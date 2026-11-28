#include "game_scene.h"

#include <stb_image.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>

using namespace DirectX;
namespace fs = std::filesystem;

const char* family_name(GameFamily family) {
    switch (family) {
        case GameFamily::Cloth: return "布料 (延迟)";
        case GameFamily::ClothFlat: return "无法线布料 (延迟)";
        case GameFamily::WetCloth: return "湿布料 (延迟)";
        case GameFamily::Skin: return "皮肤 (延迟 + SSS)";
        case GameFamily::Hair: return "头发 (前向)";
        case GameFamily::Pbs: return "PBS (前向)";
        default: return "?";
    }
}

namespace {

bool read_file(const fs::path& path, std::string& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f)
        return false;
    std::ostringstream s;
    s << f.rdbuf();
    out = s.str();
    return true;
}

XMFLOAT4 f4(const Json& j, XMFLOAT4 fallback = {}) {
    if (j.type != Json::Array)
        return fallback;
    return {j[0].as_float(), j[1].as_float(), j[2].as_float(), j[3].as_float()};
}

void f3(const Json& j, float out[3]) {
    for (int i = 0; i < 3; ++i)
        out[i] = j[i].as_float();
}

GameFamily parse_family(const std::string& s) {
    if (s == "cloth") return GameFamily::Cloth;
    if (s == "cloth_flat") return GameFamily::ClothFlat;
    if (s == "wet_cloth") return GameFamily::WetCloth;
    if (s == "skin") return GameFamily::Skin;
    if (s == "hair") return GameFamily::Hair;
    return GameFamily::Pbs;
}

MaterialRow parse_row(const Json& r) {
    MaterialRow row{};
    row.base_color = f4(r["base_color"]);
    row.specular = f4(r["specular"]);
    row.ibl_diffuse = f4(r["ibl_diffuse"]);
    row.ibl_specular = f4(r["ibl_specular"]);
    row.rim = f4(r["rim"]);
    row.velvety = f4(r["velvety"]);
    row.velvety_rim = f4(r["velvety_rim_param"]);
    row.ambient = f4(r["ambient"]);
    row.emissive = r["emissive"].as_float();
    row.scatter_rate = r["light_scatter_out_scatter_rate"].as_float();
    row.scatter_depth_offset = r["light_scatter_depth_offset"].as_float();
    row.flags = uint32_t(r["flags"].as_int());
    return row;
}

// family constant blocks, in the order of GameDraw.params (shaders/game_*.hlsl)
const std::vector<const char*>& family_params(GameFamily family) {
    static const std::vector<const char*> skin = {
        "gSkinSweatParameter", "gSkinSweatDropSpecularColor", "gSkinSweatDropIblSpecularColor",
        "gSkinSweatMaterialParameter", "gSkinSuntanColor", "gTranslucencyLightParam", "gWetLightColor",
        "gWetLightDir", "gSkinFlushParam"};
    static const std::vector<const char*> wet = {"gWetClothAbsParameter"};
    static const std::vector<const char*> hair = {"gHairParameter", "gHairSpecularColorPrimary",
                                                  "gHairSpecularColorSecondary", "gHairExtraParameter"};
    static const std::vector<const char*> none;
    return family == GameFamily::Skin ? skin : family == GameFamily::WetCloth ? wet : family == GameFamily::Hair ? hair : none;
}

// DX10-header DDS cube map with mips, as written by tools\rdc_dump.py
ComPtr<ID3D11ShaderResourceView> load_cube(ID3D11Device* device, const fs::path& path, std::string& error) {
    std::string data;
    if (!read_file(path, data) || data.size() < 148 || data.compare(0, 4, "DDS ") != 0 || data.compare(84, 4, "DX10") != 0) {
        error = "不是 DX10 DDS: " + path.string();
        return nullptr;
    }
    auto u32 = [&](size_t at) {
        uint32_t v;
        std::memcpy(&v, data.data() + at, 4);
        return v;
    };
    uint32_t height = u32(12), width = u32(16), mips = std::max(u32(28), 1u);
    auto format = DXGI_FORMAT(u32(128));
    uint32_t misc = u32(136), array = std::max(u32(140), 1u);
    if (format != DXGI_FORMAT_R16G16B16A16_FLOAT || !(misc & 4)) {
        error = "只支持 RGBA16F 立方体贴图: " + path.string();
        return nullptr;
    }
    uint32_t faces = 6 * array;
    std::vector<D3D11_SUBRESOURCE_DATA> init;
    size_t offset = 148;
    for (uint32_t f = 0; f < faces; ++f)
        for (uint32_t m = 0; m < mips; ++m) {
            uint32_t w = std::max(width >> m, 1u), h = std::max(height >> m, 1u);
            size_t bytes = size_t(w) * h * 8;
            if (offset + bytes > data.size()) {
                error = "DDS 数据不完整: " + path.string();
                return nullptr;
            }
            init.push_back({data.data() + offset, w * 8, 0});
            offset += bytes;
        }
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width = width;
    desc.Height = height;
    desc.MipLevels = mips;
    desc.ArraySize = faces;
    desc.Format = format;
    desc.SampleDesc.Count = 1;
    desc.Usage = D3D11_USAGE_IMMUTABLE;
    desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    desc.MiscFlags = D3D11_RESOURCE_MISC_TEXTURECUBE;
    ComPtr<ID3D11Texture2D> tex;
    ComPtr<ID3D11ShaderResourceView> srv;
    if (FAILED(device->CreateTexture2D(&desc, init.data(), &tex)) ||
        FAILED(device->CreateShaderResourceView(tex.Get(), nullptr, &srv))) {
        error = "立方体贴图创建失败: " + path.string();
        return nullptr;
    }
    return srv;
}

ComPtr<ID3D11ShaderResourceView> buffer_view(ID3D11Device* device, const std::string& data, uint32_t stride, bool raw) {
    D3D11_BUFFER_DESC desc{};
    desc.ByteWidth = UINT(data.size());
    desc.Usage = D3D11_USAGE_IMMUTABLE;
    desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    desc.MiscFlags = raw ? D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS : D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;
    desc.StructureByteStride = raw ? 0 : stride;
    D3D11_SUBRESOURCE_DATA init{data.data(), 0, 0};
    ComPtr<ID3D11Buffer> buffer;
    ComPtr<ID3D11ShaderResourceView> srv;
    if (FAILED(device->CreateBuffer(&desc, &init, &buffer)))
        return nullptr;
    D3D11_SHADER_RESOURCE_VIEW_DESC view{};
    if (raw) {
        view.Format = DXGI_FORMAT_R32_TYPELESS;
        view.ViewDimension = D3D11_SRV_DIMENSION_BUFFEREX;
        view.BufferEx.NumElements = UINT(data.size() / 4);
        view.BufferEx.Flags = D3D11_BUFFEREX_SRV_FLAG_RAW;
    } else {
        view.Format = DXGI_FORMAT_UNKNOWN;
        view.ViewDimension = D3D11_SRV_DIMENSION_BUFFER;
        view.Buffer.NumElements = UINT(data.size() / stride);
    }
    device->CreateShaderResourceView(buffer.Get(), &view, &srv);
    return srv;
}

std::string role_prefix(PartRole role) {
    switch (role) {
        case PartRole::Costume: return "models/costume/";
        case PartRole::Hair: return "models/hair/";
        case PartRole::Face: return "models/face/";
        default: return "";
    }
}

void set_id(GameDrawConstants& c, int id) {
    c.id_fresnel.x = float(id & 255) / 255.0f;
    c.id_fresnel.y = float((id >> 8) & 255) / 255.0f;
}

}  // namespace

bool GameScene::load(const fs::path& scene_dir, Renderer& renderer, std::string& error) {
    dir = scene_dir;
    std::string text;
    if (!read_file(dir / "scene.json", text)) {
        error = "没有 " + (dir / "scene.json").string() + "，先运行 tools\\rdc_scene.py";
        return false;
    }
    Json s = Json::parse(text.c_str());
    yaw = s["character"]["yaw"].as_float();

    const Json& set = s["light_sets"]["character"];
    for (int i = 0; i < 3; ++i) {
        const Json& l = s["lights"][size_t(set[i].as_int(i))];
        f3(l["dir"], captured_lights[i].dir);
        XMFLOAT4 c = f4(l["color"]);
        captured_lights[i].color[0] = c.x, captured_lights[i].color[1] = c.y;
        captured_lights[i].color[2] = c.z, captured_lights[i].color[3] = c.w;
    }
    reset_lights();
    const Json& hemi = s["hemispheres"][0];
    f3(hemi["dir"], hemi_dir);
    f3(hemi["sky"], hemi_sky);
    f3(hemi["ground"], hemi_ground);

    const Json& tone = s["tonemap"];
    exposure = tone["exposure"].as_float(1);
    const Json& bs = tone["bloom_scale"];
    bloom_scale = bs.type == Json::Array ? bs[0].as_float(2) : bs.as_float(2);
    for (int i = 0; i < 256; ++i)
        tone_curve_[i] = tone["curve"][size_t(i)].as_float(1);
    const Json& bloom = s["bloom"];
    bloom_offset_ = f4(bloom["offset"]);
    bloom_scale_ = f4(bloom["scale"]);
    for (int i = 0; i < 8; ++i)
        bloom_weights_[i] = bloom["weights"][size_t(i)].as_float();
    bloom_step_ = bloom["step"].as_float(1);
    const Json& sss = s["sss"];
    sss_rate_ = f4(sss["rate"]);
    for (int i = 0; i < 4; ++i)
        sss_blur_[i] = f4(sss["blur_param"][size_t(i)]);
    for (int i = 0; i < 20; ++i)
        sss_kernel_[i] = f4(sss["kernel"][size_t(i)]);

    pbs.clear();
    for (auto& p : s["pbs"].items)
        pbs.push_back({p["name"].text, p["id"].as_int(), parse_row(p["row"])});

    ID3D11Device* device = renderer.device();
    std::string table, skin;
    if (!read_file(dir / "materials.bin", table) || table.size() < 144 || !read_file(dir / "skin_materials.bin", skin) ||
        skin.size() < 112) {
        error = "材质表 materials.bin / skin_materials.bin 缺失";
        return false;
    }
    material_table = buffer_view(device, table, 144, false);
    skin_table = buffer_view(device, skin, 0, true);
    ibl_diffuse = load_cube(device, dir / s["ibl"]["diffuse"].text, error);
    ibl_specular = load_cube(device, dir / s["ibl"]["specular"].text, error);
    if (!material_table || !skin_table || !ibl_diffuse || !ibl_specular) {
        if (error.empty())
            error = "场景资源创建失败";
        return false;
    }
    int w = 0, h = 0, n = 0;
    std::u8string suntan_path = (dir / s["suntan"].text).u8string();
    if (unsigned char* pixels = stbi_load(reinterpret_cast<const char*>(suntan_path.c_str()), &w, &h, &n, 4)) {
        suntan = renderer.create_texture(pixels, w, h);
        stbi_image_free(pixels);
    }

    captured_.clear();
    cache_.clear();
    for (auto& [glb, mats] : s["materials"].fields)
        for (auto& [name, m] : mats.fields)
            captured_[glb][name] = parse_material(m);
    for (auto& t : templates_)
        t = GameMaterial();
    hair_blended_ = GameMaterial();
    bool have[int(GameFamily::Count)] = {};
    for (auto& [glb, mats] : captured_)
        for (auto& [name, m] : mats) {
            int f = int(m.family);
            bool opaque = std::any_of(m.passes.begin(), m.passes.end(), [](const GamePass& p) { return !p.blend; });
            if (m.family == GameFamily::Hair && !opaque) {
                if (hair_blended_.passes.empty()) {
                    hair_blended_ = m;
                    hair_blended_.source = glb + " " + name;
                }
                continue;
            }
            if (!have[f]) {
                have[f] = true;
                templates_[f] = m;
                templates_[f].source = glb + " " + name;
            }
        }
    if (hair_blended_.passes.empty())
        hair_blended_ = templates_[int(GameFamily::Hair)];
    loaded_ = true;
    return true;
}

GamePass GameScene::parse_pass(const Json& p, GameFamily family, uint32_t flags) const {
    GamePass out;
    out.blend = p["blend"].number != 0;
    out.depth_write = p["depth_write"].number != 0;
    out.cull_back = p["cull"].text == "Back";
    out.event = p["event"].as_int();
    out.stencil = family == GameFamily::Skin ? 5 : is_deferred(family) ? 4 : 0;
    for (int t = 0; t < 4; ++t)
        out.srgb[t] = p["textures"]["t" + std::to_string(t)].text.find("SRGB") != std::string::npos;

    GameDrawConstants& c = out.constants;
    const Json& cb = p["cb"];
    c.flags = flags;
    c.hdr_rate = f4(cb["gHDRRate"], c.hdr_rate);
    c.id_fresnel = f4(cb["gIDandFresnel"]);
    c.reflection_color = f4(cb["gReflectionColor"]);
    c.reflection_visibility = f4(cb["gReflectionVisibilityParam"], c.reflection_visibility);
    c.ibl_diffuse = f4(cb["gIblDiffuseColor"]);
    c.ibl_specular = f4(cb["gIblSpecularColor"]);
    c.velvety_rim = f4(cb["gVelvetyRimParam"], c.velvety_rim);
    c.specular = f4(cb["gSpecularColor"]);
    c.spec_visibility = f4(cb["gSpecularVisibilityParam"], c.spec_visibility);
    c.velvety = f4(cb["gVelvetyColor"]);
    c.rim = f4(cb["gRimColor"]);
    c.mul_color = f4(cb["gMaterialMulColor"], c.mul_color);
    c.add_color = f4(cb["gMaterialAddColor"], c.add_color);
    c.material_param = f4(cb["gMaterialParam"], c.material_param);
    c.material_param2 = f4(cb["gMaterialParam2"]);
    const Json& ambient = p["ambient"];
    if (ambient.type == Json::Array) {
        c.ambient[0] = f4(ambient[0]);
        c.ambient[1] = f4(ambient[1]);
    }
    const auto& names = family_params(family);
    for (size_t i = 0; i < names.size(); ++i)
        c.params[i] = f4(p["params"][names[i]]);
    return out;
}

GameMaterial GameScene::parse_material(const Json& m) const {
    GameMaterial out;
    out.family = parse_family(m["family"].text);
    out.captured = true;
    out.source = "抓帧";
    uint32_t flags = 0;
    for (auto& f : m["flags"].items) {
        if (f.text == "normal_map") flags |= GameNormalMap;
        if (f.text == "spec_map") flags |= GameSpecMap;
        if (f.text == "spec_albedo") flags |= GameSpecAlbedo;
        if (f.text == "reflection_map") flags |= GameReflectionMap;
        if (f.text == "diffuse_only") flags |= GameDiffuseOnly;
    }
    if (out.family == GameFamily::Hair)
        flags |= GameNormalMap;
    for (auto& p : m["passes"].items)
        out.passes.push_back(parse_pass(p, out.family, flags));
    if (is_deferred(out.family)) {
        int index = m["material_id"].as_int() - (pbs.empty() ? 0 : pbs[0].id);
        if (index >= 0 && index < int(pbs.size()))
            out.pbs = index;
    }
    out.original = out.passes;
    out.original_pbs = out.pbs;
    return out;
}

GameMaterial& GameScene::material(const Part& part, int material_index) {
    const ModelMaterial& mat = part.model->materials[size_t(material_index)];
    std::string key = part.glb + "|" + mat.name;
    auto it = cache_.find(key);
    if (it != cache_.end())
        return it->second;
    GameMaterial& out = cache_[key];
    auto glb = captured_.find(part.glb);
    if (glb != captured_.end()) {
        if (glb->second.count(mat.name)) {
            out = glb->second.at(mat.name);
            return out;
        }
        out.hidden = true;
    }
    // faces share one material layout, so another captured face is the best guess
    std::string prefix = role_prefix(part.role);
    if (part.role == PartRole::Face)
        for (auto& [other, mats] : captured_)
            if (other.rfind(prefix, 0) == 0 && mats.count(mat.name)) {
                out = mats.at(mat.name);
                out.captured = false;
                out.source = "推测：抓帧里另一张脸的同名材质 (" + other + ")";
                return out;
            }
    GameFamily family = GameFamily::Cloth;
    bool blend = mat.alpha_mode == 2;
    if (part.role == PartRole::Hair)
        family = GameFamily::Hair;
    else if (blend)
        family = GameFamily::Pbs;
    else if (part.role == PartRole::Costume && mat.name == "mtl0_0")
        family = GameFamily::Skin;
    else if (!mat.slot(1) || !mat.slot(2))
        family = GameFamily::ClothFlat;
    bool hidden = out.hidden;
    set_family(out, family, mat);
    out.hidden = hidden;
    if (hidden)
        out.source = "抓帧里没有画这个材质（默认隐藏）；" + out.source;
    return out;
}

void GameScene::set_family(GameMaterial& m, GameFamily family, const ModelMaterial& source) {
    bool blend = source.alpha_mode == 2;
    const GameMaterial& t = family == GameFamily::Hair && blend ? hair_blended_ : templates_[int(family)];
    bool hidden = m.hidden;
    m = t;
    m.hidden = hidden;
    m.captured = false;
    m.source = std::string("推测：") + family_name(family) + "，模板 " + t.source;
    for (auto& p : m.passes) {
        if (!source.slot(1))
            p.constants.flags &= ~uint32_t(GameNormalMap | GameReflectionMap);
        if (!source.slot(2))
            p.constants.flags &= ~uint32_t(GameSpecMap);
    }
    m.original = m.passes;
    m.original_pbs = m.pbs;
}

void GameScene::set_pbs(GameMaterial& m, int index) {
    if (index < 0 || index >= int(pbs.size())) {
        m.passes = m.original;
        m.pbs = m.original_pbs;
        return;
    }
    m.pbs = index;
    const MaterialRow& row = pbs[size_t(index)].row;
    for (auto& p : m.passes) {
        GameDrawConstants& c = p.constants;
        if (is_deferred(m.family)) {
            set_id(c, pbs[size_t(index)].id);
            continue;
        }
        c.specular = row.specular;
        c.ibl_diffuse = row.ibl_diffuse;
        c.ibl_specular = row.ibl_specular;
        c.velvety_rim = row.velvety_rim;
        c.velvety = row.velvety;
        c.rim = row.rim;
        c.ambient[0] = {hemi_sky[0] * row.ambient.x, hemi_sky[1] * row.ambient.y, hemi_sky[2] * row.ambient.z, 0};
        c.ambient[1] = {hemi_ground[0] * row.ambient.x, hemi_ground[1] * row.ambient.y, hemi_ground[2] * row.ambient.z, 0};
    }
}

void GameScene::reset_lights() {
    for (int i = 0; i < 3; ++i)
        lights[i] = captured_lights[i];
}

void GameScene::fill_frame(GameFrameConstants& f) const {
    for (int i = 0; i < 3; ++i) {
        const GameLight& l = lights[i];
        XMVECTOR d = XMVector3Normalize(XMVectorSet(l.dir[0], l.dir[1], l.dir[2], 0));
        XMStoreFloat4(&f.light_dir[i], d);
        f.light_color[i] = {l.color[0], l.color[1], l.color[2], l.color[3]};
    }
    f.hemi_dir = {hemi_dir[0], hemi_dir[1], hemi_dir[2], 0};
    f.hemi_sky = {hemi_sky[0], hemi_sky[1], hemi_sky[2], 0};
    f.hemi_ground = {hemi_ground[0], hemi_ground[1], hemi_ground[2], 0};
    float c = std::cos(yaw), s = std::sin(yaw);
    f.env_rot[0] = {c, 0, s, 0};
    f.env_rot[1] = {0, 1, 0, 0};
    f.env_rot[2] = {-s, 0, c, 0};
    f.depth_param.w = ibl_strength;
    f.sss_rate = sss_rate_;
    std::copy(std::begin(sss_blur_), std::end(sss_blur_), f.sss_blur);
    std::copy(std::begin(sss_kernel_), std::end(sss_kernel_), f.sss_kernel);
    f.bloom_offset = bloom_offset_;
    f.bloom_scale = bloom_scale_;
    f.bloom_weights[0] = {bloom_weights_[0], bloom_weights_[1], bloom_weights_[2], bloom_weights_[3]};
    f.bloom_weights[1] = {bloom_weights_[4], bloom_weights_[5], bloom_weights_[6], bloom_weights_[7]};
    f.tone = {exposure, bloom_scale, bloom_step_, 0};
    std::copy(std::begin(tone_curve_), std::end(tone_curve_), f.tone_curve);
}
