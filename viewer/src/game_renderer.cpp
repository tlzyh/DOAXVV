#include "game_renderer.h"

#include <algorithm>
#include <cmath>
#include <cstring>

using namespace DirectX;

namespace {

struct PassConstants {
    float dir[4];
    uint32_t combine;
    uint32_t pad[3];
};

ComPtr<ID3D11Buffer> constant_buffer(ID3D11Device* device, size_t bytes) {
    D3D11_BUFFER_DESC desc{};
    desc.ByteWidth = UINT((bytes + 15) & ~size_t(15));
    desc.Usage = D3D11_USAGE_DYNAMIC;
    desc.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
    ComPtr<ID3D11Buffer> buffer;
    device->CreateBuffer(&desc, nullptr, &buffer);
    return buffer;
}

void upload(ID3D11DeviceContext* context, ID3D11Buffer* buffer, const void* data, size_t bytes) {
    D3D11_MAPPED_SUBRESOURCE mapped;
    if (SUCCEEDED(context->Map(buffer, 0, D3D11_MAP_WRITE_DISCARD, 0, &mapped))) {
        std::memcpy(mapped.pData, data, bytes);
        context->Unmap(buffer, 0);
    }
}

void viewport(ID3D11DeviceContext* c, int width, int height) {
    D3D11_VIEWPORT vp{0, 0, float(width), float(height), 0, 1};
    c->RSSetViewports(1, &vp);
}

void unbind(ID3D11DeviceContext* c) {
    ID3D11ShaderResourceView* srvs[16] = {};
    ID3D11UnorderedAccessView* uavs[4] = {};
    c->OMSetRenderTargets(0, nullptr, nullptr);
    c->PSSetShaderResources(0, 16, srvs);
    c->CSSetShaderResources(0, 16, srvs);
    c->CSSetUnorderedAccessViews(0, 4, uavs, nullptr);
}

}  // namespace

bool GameRenderer::reload(Renderer& renderer, std::string& log) {
    device_ = renderer.device();
    auto dir = renderer.shader_dir;
    auto gbuffer = dir / "game_gbuffer.hlsl", forward = dir / "game_forward.hlsl";
    auto lighting = dir / "game_lighting.hlsl", post = dir / "game_post.hlsl";
    auto vs = renderer.compile(gbuffer, "vs_main", "vs_5_0", log);
    const char* entries[] = {"ps_cloth", "ps_cloth_flat", "ps_wet_cloth", "ps_skin", "ps_hair", "ps_pbs"};
    ComPtr<ID3DBlob> family[int(GameFamily::Count)];
    for (int f = 0; f < int(GameFamily::Count); ++f)
        family[f] = renderer.compile(f < 4 ? gbuffer : forward, entries[f], "ps_5_0", log);
    auto cs = renderer.compile(lighting, "cs_main", "cs_5_0", log);
    auto fvs = renderer.compile(post, "vs_fullscreen", "vs_5_0", log);
    auto sss = renderer.compile(post, "ps_sss", "ps_5_0", log), bright = renderer.compile(post, "ps_bright", "ps_5_0", log);
    auto blur = renderer.compile(post, "ps_blur", "ps_5_0", log), tone = renderer.compile(post, "ps_tonemap", "ps_5_0", log);
    if (!vs || !cs || !fvs || !sss || !bright || !blur || !tone ||
        std::any_of(std::begin(family), std::end(family), [](auto& b) { return !b; }))
        return false;

    auto elements = vertex_elements();
    auto ps = [&](ID3DBlob* b, ComPtr<ID3D11PixelShader>& out) {
        return SUCCEEDED(device_->CreatePixelShader(b->GetBufferPointer(), b->GetBufferSize(), nullptr, &out));
    };
    ComPtr<ID3D11VertexShader> new_vs, new_fvs;
    ComPtr<ID3D11InputLayout> new_layout;
    ComPtr<ID3D11ComputeShader> new_cs;
    ComPtr<ID3D11PixelShader> new_family[int(GameFamily::Count)], new_sss, new_bright, new_blur, new_tone;
    bool ok = SUCCEEDED(device_->CreateVertexShader(vs->GetBufferPointer(), vs->GetBufferSize(), nullptr, &new_vs)) &&
              SUCCEEDED(device_->CreateInputLayout(elements.data(), UINT(elements.size()), vs->GetBufferPointer(),
                                                   vs->GetBufferSize(), &new_layout)) &&
              SUCCEEDED(device_->CreateVertexShader(fvs->GetBufferPointer(), fvs->GetBufferSize(), nullptr, &new_fvs)) &&
              SUCCEEDED(device_->CreateComputeShader(cs->GetBufferPointer(), cs->GetBufferSize(), nullptr, &new_cs)) &&
              ps(sss.Get(), new_sss) && ps(bright.Get(), new_bright) && ps(blur.Get(), new_blur) && ps(tone.Get(), new_tone);
    for (int f = 0; ok && f < int(GameFamily::Count); ++f)
        ok = ps(family[f].Get(), new_family[f]);
    if (!ok) {
        log += "game shader object creation failed\n";
        return false;
    }
    mesh_vs_ = new_vs;
    layout_ = new_layout;
    fullscreen_vs_ = new_fvs;
    lighting_cs_ = new_cs;
    for (int f = 0; f < int(GameFamily::Count); ++f)
        family_ps_[f] = new_family[f];
    sss_ps_ = new_sss;
    bright_ps_ = new_bright;
    blur_ps_ = new_blur;
    tonemap_ps_ = new_tone;
    if (!frame_cb_)
        create_states(renderer);
    return true;
}

void GameRenderer::create_states(Renderer& renderer) {
    frame_cb_ = constant_buffer(device_, sizeof(GameFrameConstants));
    draw_cb_ = constant_buffer(device_, sizeof(GameDrawConstants));
    pass_cb_ = constant_buffer(device_, sizeof(PassConstants));

    D3D11_RASTERIZER_DESC raster{};
    raster.FillMode = D3D11_FILL_SOLID;
    raster.CullMode = D3D11_CULL_NONE;
    raster.DepthClipEnable = TRUE;
    // the game views the world through a mirrored (left-handed) view matrix, the viewer does not,
    // so the game's clockwise front faces reach the rasterizer counter-clockwise
    raster.FrontCounterClockwise = TRUE;
    device_->CreateRasterizerState(&raster, &cull_none_);
    raster.CullMode = D3D11_CULL_BACK;
    device_->CreateRasterizerState(&raster, &cull_back_);

    D3D11_DEPTH_STENCIL_DESC ds{};
    ds.DepthEnable = TRUE;
    ds.DepthWriteMask = D3D11_DEPTH_WRITE_MASK_ALL;
    ds.DepthFunc = D3D11_COMPARISON_LESS_EQUAL;
    device_->CreateDepthStencilState(&ds, &ds_write_);
    ds.DepthWriteMask = D3D11_DEPTH_WRITE_MASK_ZERO;
    device_->CreateDepthStencilState(&ds, &ds_read_);
    ds.DepthWriteMask = D3D11_DEPTH_WRITE_MASK_ALL;
    ds.StencilEnable = TRUE;
    ds.StencilReadMask = ds.StencilWriteMask = 0xFF;
    ds.FrontFace = {D3D11_STENCIL_OP_KEEP, D3D11_STENCIL_OP_KEEP, D3D11_STENCIL_OP_REPLACE, D3D11_COMPARISON_ALWAYS};
    ds.BackFace = ds.FrontFace;
    device_->CreateDepthStencilState(&ds, &ds_gbuffer_);
    ds.DepthEnable = FALSE;
    ds.StencilReadMask = 15;
    ds.StencilWriteMask = 0;
    ds.FrontFace = {D3D11_STENCIL_OP_KEEP, D3D11_STENCIL_OP_KEEP, D3D11_STENCIL_OP_KEEP, D3D11_COMPARISON_EQUAL};
    ds.BackFace = ds.FrontFace;
    device_->CreateDepthStencilState(&ds, &ds_sss_);

    D3D11_BLEND_DESC blend{};
    blend.IndependentBlendEnable = FALSE;
    blend.RenderTarget[0].RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_ALL;
    device_->CreateBlendState(&blend, &bs_opaque_);
    blend.RenderTarget[0].RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_RED | D3D11_COLOR_WRITE_ENABLE_GREEN |
                                                  D3D11_COLOR_WRITE_ENABLE_BLUE;
    device_->CreateBlendState(&blend, &bs_rgb_);
    auto& rt = blend.RenderTarget[0];
    rt.BlendEnable = TRUE;
    rt.SrcBlend = D3D11_BLEND_SRC_ALPHA;
    rt.DestBlend = D3D11_BLEND_INV_SRC_ALPHA;
    rt.BlendOp = D3D11_BLEND_OP_ADD;
    rt.SrcBlendAlpha = D3D11_BLEND_ONE;
    rt.DestBlendAlpha = D3D11_BLEND_ZERO;
    rt.BlendOpAlpha = D3D11_BLEND_OP_ADD;
    device_->CreateBlendState(&blend, &bs_alpha_);

    D3D11_SAMPLER_DESC sampler{};
    sampler.Filter = D3D11_FILTER_ANISOTROPIC;
    sampler.MaxAnisotropy = 8;
    sampler.AddressU = sampler.AddressV = sampler.AddressW = D3D11_TEXTURE_ADDRESS_WRAP;
    sampler.MaxLOD = D3D11_FLOAT32_MAX;
    device_->CreateSamplerState(&sampler, &wrap_);
    sampler.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sampler.AddressU = sampler.AddressV = sampler.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
    device_->CreateSamplerState(&sampler, &clamp_);

    const uint8_t white[4] = {255, 255, 255, 255}, flat[4] = {128, 128, 255, 255};
    white_ = renderer.create_texture(white, 1, 1);
    flat_normal_ = renderer.create_texture(flat, 1, 1);
}

bool GameRenderer::make_target(Target& t, int width, int height, DXGI_FORMAT format, bool uav, bool srgb) {
    t = Target();
    t.width = std::max(width, 1);
    t.height = std::max(height, 1);
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width = UINT(t.width);
    desc.Height = UINT(t.height);
    desc.MipLevels = desc.ArraySize = 1;
    desc.Format = srgb ? DXGI_FORMAT_R8G8B8A8_TYPELESS : format;
    desc.SampleDesc.Count = 1;
    desc.BindFlags = D3D11_BIND_RENDER_TARGET | D3D11_BIND_SHADER_RESOURCE | (uav ? D3D11_BIND_UNORDERED_ACCESS : 0);
    if (FAILED(device_->CreateTexture2D(&desc, nullptr, &t.texture)))
        return false;
    D3D11_RENDER_TARGET_VIEW_DESC rtv{};
    rtv.Format = format;
    rtv.ViewDimension = D3D11_RTV_DIMENSION_TEXTURE2D;
    D3D11_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.Format = format;
    srv.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
    srv.Texture2D.MipLevels = 1;
    if (FAILED(device_->CreateRenderTargetView(t.texture.Get(), &rtv, &t.rtv)) ||
        FAILED(device_->CreateShaderResourceView(t.texture.Get(), &srv, &t.srv)))
        return false;
    return !uav || SUCCEEDED(device_->CreateUnorderedAccessView(t.texture.Get(), nullptr, &t.uav));
}

bool GameRenderer::ensure_targets(Renderer& renderer) {
    int w = renderer.width(), h = renderer.height();
    if (w == width_ && h == height_ && depth_)
        return true;
    width_ = w;
    height_ = h;
    const DXGI_FORMAT half = DXGI_FORMAT_R16G16B16A16_FLOAT, unorm = DXGI_FORMAT_R8G8B8A8_UNORM;
    bool ok = make_target(gbuffer_[0], w, h, DXGI_FORMAT_R8G8B8A8_UNORM_SRGB, false, true) &&
              make_target(gbuffer_[1], w, h, half, false) && make_target(gbuffer_[2], w, h, unorm, false) &&
              make_target(gbuffer_[3], w, h, unorm, false) && make_target(gbuffer_[4], w, h, half, false) &&
              make_target(hdr_, w, h, half, true) && make_target(skin_diffuse_, w, h, half, true) &&
              make_target(material_diffuse_, w, h, half, true) && make_target(skin_specular_, w, h, half, true) &&
              make_target(sss_temp_, w, h, half, false) && make_target(bloom_[0], w / 4, h / 4, half, false) &&
              make_target(bloom_[1], w / 4, h / 8, half, false) && make_target(bloom_[2], w / 8, h / 8, half, false);
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width = UINT(w);
    desc.Height = UINT(h);
    desc.MipLevels = desc.ArraySize = 1;
    desc.Format = DXGI_FORMAT_R24G8_TYPELESS;
    desc.SampleDesc.Count = 1;
    desc.BindFlags = D3D11_BIND_DEPTH_STENCIL | D3D11_BIND_SHADER_RESOURCE;
    depth_.Reset();
    dsv_.Reset();
    dsv_read_only_.Reset();
    depth_srv_.Reset();
    stencil_srv_.Reset();
    D3D11_DEPTH_STENCIL_VIEW_DESC dsv{};
    dsv.Format = DXGI_FORMAT_D24_UNORM_S8_UINT;
    dsv.ViewDimension = D3D11_DSV_DIMENSION_TEXTURE2D;
    D3D11_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
    srv.Texture2D.MipLevels = 1;
    ok = ok && SUCCEEDED(device_->CreateTexture2D(&desc, nullptr, &depth_)) &&
         SUCCEEDED(device_->CreateDepthStencilView(depth_.Get(), &dsv, &dsv_));
    dsv.Flags = D3D11_DSV_READ_ONLY_DEPTH | D3D11_DSV_READ_ONLY_STENCIL;
    ok = ok && SUCCEEDED(device_->CreateDepthStencilView(depth_.Get(), &dsv, &dsv_read_only_));
    srv.Format = DXGI_FORMAT_R24_UNORM_X8_TYPELESS;
    ok = ok && SUCCEEDED(device_->CreateShaderResourceView(depth_.Get(), &srv, &depth_srv_));
    srv.Format = DXGI_FORMAT_X24_TYPELESS_G8_UINT;
    ok = ok && SUCCEEDED(device_->CreateShaderResourceView(depth_.Get(), &srv, &stencil_srv_));
    if (!ok)
        depth_.Reset();
    return ok;
}

void GameRenderer::gather(Character& character, GameScene& scene, Renderer& renderer, const XMMATRIX& view,
                          std::vector<XMFLOAT4X4>& joints, std::vector<GameDrawItem>& items,
                          const ModelMaterial* highlight) {
    if (!white_)
        return;
    std::vector<PrimitiveDraw> draws;
    character.collect(view, joints, draws);
    for (auto& d : draws) {
        GltfModel& model = *d.part->model;
        const ModelPrimitive& prim = model.primitives[d.primitive];
        if (prim.material < 0)
            continue;
        const ModelMaterial& mat = model.materials[size_t(prim.material)];
        GameDrawItem item;
        item.primitive = &prim;
        item.material = &scene.material(*d.part, prim.material);
        if (item.material->hidden)
            continue;
        item.depth = d.depth;
        for (size_t p = 0; p < std::min<size_t>(item.material->passes.size(), 2); ++p) {
            const GamePass& pass = item.material->passes[p];
            GameDrawConstants& c = item.constants[p];
            c = pass.constants;
            c.joint_offset = d.joint_offset;
            if (&mat == highlight)
                c.flags |= GameHighlight;
            for (int s = 0; s < 4; ++s) {
                const TextureRef* ref = mat.slot(s);
                const Texture* tex = ref ? model.texture(ref->image, renderer) : nullptr;
                c.uv_set[s] = ref ? uint32_t(ref->uv) : 0;
                if (!tex)
                    tex = s == 1 || (s == 2 && item.material->family == GameFamily::WetCloth) ? flat_normal_.get()
                                                                                              : white_.get();
                item.textures[p][s] = pass.srgb[s] ? tex->srgb.Get() : tex->linear.Get();
            }
        }
        items.push_back(item);
    }
}

void GameRenderer::draw_items(ID3D11DeviceContext* c, const std::vector<GameDrawItem>& items, bool deferred) {
    struct Entry {
        const GameDrawItem* item;
        size_t pass;
    };
    std::vector<Entry> list;
    for (auto& item : items) {
        if (is_deferred(item.material->family) != deferred)
            continue;
        for (size_t p = 0; p < std::min<size_t>(item.material->passes.size(), 2); ++p)
            list.push_back({&item, p});
    }
    // opaque first in model order, then blended in capture order, far to near within a draw
    std::stable_sort(list.begin(), list.end(), [](const Entry& a, const Entry& b) {
        const GamePass &pa = a.item->material->passes[a.pass], &pb = b.item->material->passes[b.pass];
        if (pa.blend != pb.blend)
            return pb.blend;
        if (!pa.blend)
            return false;
        if (pa.event != pb.event)
            return pa.event < pb.event;
        return a.item->depth > b.item->depth;
    });
    const float factor[4] = {};
    for (auto& e : list) {
        const GamePass& pass = e.item->material->passes[e.pass];
        c->RSSetState(pass.cull_back ? cull_back_.Get() : cull_none_.Get());
        if (deferred) {
            c->OMSetDepthStencilState(ds_gbuffer_.Get(), UINT(pass.stencil));
            c->OMSetBlendState(bs_opaque_.Get(), factor, 0xFFFFFFFF);
        } else {
            c->OMSetDepthStencilState(pass.depth_write ? ds_write_.Get() : ds_read_.Get(), 0);
            c->OMSetBlendState(pass.blend ? bs_alpha_.Get() : bs_opaque_.Get(), factor, 0xFFFFFFFF);
        }
        c->PSSetShader(family_ps_[int(e.item->material->family)].Get(), nullptr, 0);
        upload(c, draw_cb_.Get(), &e.item->constants[e.pass], sizeof(GameDrawConstants));
        c->PSSetShaderResources(0, 4, e.item->textures[e.pass]);
        const ModelPrimitive& prim = *e.item->primitive;
        UINT stride = sizeof(Vertex), offset = 0;
        ID3D11Buffer* vb = prim.vertices.Get();
        c->IASetVertexBuffers(0, 1, &vb, &stride, &offset);
        c->IASetIndexBuffer(prim.indices.Get(), prim.index_format, 0);
        c->DrawIndexed(prim.index_count, 0, 0);
    }
}

void GameRenderer::fullscreen(ID3D11DeviceContext* c, ID3D11PixelShader* ps, const Target& target, float dir_x,
                              float dir_y, uint32_t combine) {
    PassConstants pass{{dir_x, dir_y, 0, 0}, combine, {}};
    upload(c, pass_cb_.Get(), &pass, sizeof(pass));
    viewport(c, target.width, target.height);
    c->PSSetShader(ps, nullptr, 0);
    c->Draw(3, 0);
}

void GameRenderer::render(Renderer& renderer, const GameScene& scene, const std::vector<GameDrawItem>& items,
                          GameFrameConstants& frame, const float background[3]) {
    if (!ready() || !ensure_targets(renderer))
        return;
    ID3D11DeviceContext* c = renderer.context();
    frame.screen = {float(width_), float(height_), 1.0f / float(width_), 1.0f / float(height_)};
    upload(c, frame_cb_.Get(), &frame, sizeof(frame));
    ID3D11Buffer* cbs[] = {frame_cb_.Get(), draw_cb_.Get(), pass_cb_.Get()};
    ID3D11SamplerState* samplers[] = {wrap_.Get(), clamp_.Get()};
    ID3D11ShaderResourceView* ibl[] = {scene.ibl_diffuse.Get(), scene.ibl_specular.Get()};
    const float zero[4] = {}, clear[4] = {background[0], background[1], background[2], 0};

    // G-buffer
    unbind(c);
    for (auto& g : gbuffer_)
        c->ClearRenderTargetView(g.rtv.Get(), zero);
    c->ClearRenderTargetView(hdr_.rtv.Get(), clear);
    c->ClearDepthStencilView(dsv_.Get(), D3D11_CLEAR_DEPTH | D3D11_CLEAR_STENCIL, 1.0f, 0);
    ID3D11RenderTargetView* gb[5];
    for (int i = 0; i < 5; ++i)
        gb[i] = gbuffer_[i].rtv.Get();
    c->OMSetRenderTargets(5, gb, dsv_.Get());
    viewport(c, width_, height_);
    c->IASetInputLayout(layout_.Get());
    c->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    c->VSSetShader(mesh_vs_.Get(), nullptr, 0);
    c->VSSetConstantBuffers(0, 2, cbs);
    c->PSSetConstantBuffers(0, 3, cbs);
    ID3D11ShaderResourceView* joints = renderer.joints();
    c->VSSetShaderResources(16, 1, &joints);
    c->PSSetSamplers(0, 2, samplers);
    ID3D11ShaderResourceView* suntan = scene.suntan ? scene.suntan->linear.Get() : white_->linear.Get();
    c->PSSetShaderResources(4, 1, &suntan);
    c->PSSetShaderResources(8, 2, ibl);
    draw_items(c, items, true);

    // lighting
    unbind(c);
    c->ClearUnorderedAccessViewFloat(skin_diffuse_.uav.Get(), zero);
    c->ClearUnorderedAccessViewFloat(material_diffuse_.uav.Get(), zero);
    c->ClearUnorderedAccessViewFloat(skin_specular_.uav.Get(), zero);
    ID3D11ShaderResourceView* cs_srvs[11] = {gbuffer_[0].srv.Get(), gbuffer_[1].srv.Get(), gbuffer_[2].srv.Get(),
                                             gbuffer_[3].srv.Get(), gbuffer_[4].srv.Get(), depth_srv_.Get(),
                                             stencil_srv_.Get(),    scene.material_table.Get(), ibl[0],
                                             ibl[1],                scene.skin_table.Get()};
    ID3D11UnorderedAccessView* uavs[4] = {hdr_.uav.Get(), skin_diffuse_.uav.Get(), material_diffuse_.uav.Get(),
                                          skin_specular_.uav.Get()};
    c->CSSetShader(lighting_cs_.Get(), nullptr, 0);
    c->CSSetConstantBuffers(0, 1, cbs);
    c->CSSetSamplers(0, 2, samplers);
    c->CSSetShaderResources(0, 11, cs_srvs);
    c->CSSetUnorderedAccessViews(0, 4, uavs, nullptr);
    c->Dispatch(UINT((width_ + 7) / 8), UINT((height_ + 7) / 8), 1);
    unbind(c);

    // skin SSS, horizontal into sss_temp, vertical + combine into the HDR target
    const float factor[4] = {};
    c->IASetInputLayout(nullptr);
    c->VSSetShader(fullscreen_vs_.Get(), nullptr, 0);
    c->RSSetState(cull_none_.Get());
    c->OMSetDepthStencilState(ds_sss_.Get(), 5);
    c->OMSetBlendState(bs_opaque_.Get(), factor, 0xFFFFFFFF);
    ID3D11ShaderResourceView* sss_srvs[5] = {skin_diffuse_.srv.Get(), material_diffuse_.srv.Get(),
                                             skin_specular_.srv.Get(), gbuffer_[3].srv.Get(), depth_srv_.Get()};
    c->OMSetRenderTargets(1, sss_temp_.rtv.GetAddressOf(), dsv_read_only_.Get());
    c->PSSetShaderResources(0, 5, sss_srvs);
    fullscreen(c, sss_ps_.Get(), sss_temp_, 1, 0, 0);
    c->OMSetRenderTargets(1, hdr_.rtv.GetAddressOf(), dsv_read_only_.Get());
    sss_srvs[0] = sss_temp_.srv.Get();
    c->PSSetShaderResources(0, 5, sss_srvs);
    c->OMSetBlendState(bs_rgb_.Get(), factor, 0xFFFFFFFF);
    fullscreen(c, sss_ps_.Get(), hdr_, 0, 1, 1);
    unbind(c);

    // forward hair, eyes and transparent parts
    c->OMSetRenderTargets(1, hdr_.rtv.GetAddressOf(), dsv_.Get());
    viewport(c, width_, height_);
    c->IASetInputLayout(layout_.Get());
    c->VSSetShader(mesh_vs_.Get(), nullptr, 0);
    c->PSSetShaderResources(4, 1, &suntan);
    c->PSSetShaderResources(8, 2, ibl);
    draw_items(c, items, false);
    unbind(c);

    // bloom: bright pass at 1/4, vertical blur to 1/4 x 1/8, horizontal blur to 1/8
    c->IASetInputLayout(nullptr);
    c->VSSetShader(fullscreen_vs_.Get(), nullptr, 0);
    c->RSSetState(cull_none_.Get());
    c->OMSetDepthStencilState(nullptr, 0);
    c->OMSetBlendState(bs_opaque_.Get(), factor, 0xFFFFFFFF);
    const Target* sources[3] = {&hdr_, &bloom_[0], &bloom_[1]};
    for (int i = 0; i < 3; ++i) {
        c->OMSetRenderTargets(1, bloom_[i].rtv.GetAddressOf(), nullptr);
        c->PSSetShaderResources(0, 1, sources[i]->srv.GetAddressOf());
        if (i == 0)
            fullscreen(c, bright_ps_.Get(), bloom_[0], 0, 0, 0);
        else if (i == 1)
            fullscreen(c, blur_ps_.Get(), bloom_[1], 0, 1.0f / float(bloom_[0].height), 0);
        else
            fullscreen(c, blur_ps_.Get(), bloom_[2], 1.0f / float(bloom_[1].width), 0, 0);
        unbind(c);
    }

    // tone mapping into the UNORM backbuffer
    ID3D11RenderTargetView* back = renderer.backbuffer();
    c->OMSetRenderTargets(1, &back, nullptr);
    ID3D11ShaderResourceView* tone_srvs[13] = {hdr_.srv.Get(),        material_diffuse_.srv.Get(),
                                               skin_specular_.srv.Get(), gbuffer_[3].srv.Get(),
                                               depth_srv_.Get(),       bloom_[2].srv.Get(),
                                               gbuffer_[0].srv.Get(),  gbuffer_[1].srv.Get(),
                                               ibl[0],                 ibl[1],
                                               gbuffer_[2].srv.Get(),  stencil_srv_.Get(),
                                               skin_diffuse_.srv.Get()};
    c->PSSetShaderResources(0, 13, tone_srvs);
    Target screen;
    screen.width = width_;
    screen.height = height_;
    fullscreen(c, tonemap_ps_.Get(), screen, 0, 0, 0);
    unbind(c);
}
