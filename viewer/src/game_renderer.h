// Game render mode: G-buffer -> lighting compute shader -> skin SSS -> forward materials ->
// bloom -> tone mapping, in the pass order of the captured frame (阶段总结.md 14).
// Shaders: viewer/shaders/game_*.hlsl, reloaded together with the simple mode shaders.
#pragma once

#include "game_scene.h"

struct GameDrawItem {
    const ModelPrimitive* primitive = nullptr;
    const GameMaterial* material = nullptr;
    GameDrawConstants constants[2];  // per pass: pass constants + joint offset, uv sets, highlight
    ID3D11ShaderResourceView* textures[2][4] = {};
    float depth = 0;
};

class GameRenderer {
public:
    bool reload(Renderer& renderer, std::string& log);
    // poses come from Character::collect; uncaptured materials are guessed by GameScene::material
    void gather(Character& character, GameScene& scene, Renderer& renderer, const DirectX::XMMATRIX& view,
                std::vector<XMFLOAT4X4>& joints, std::vector<GameDrawItem>& items, const ModelMaterial* highlight);
    void render(Renderer& renderer, const GameScene& scene, const std::vector<GameDrawItem>& items,
                GameFrameConstants& frame, const float background[3]);
    bool ready() const { return lighting_cs_ != nullptr; }

private:
    struct Target {
        ComPtr<ID3D11Texture2D> texture;
        ComPtr<ID3D11RenderTargetView> rtv;
        ComPtr<ID3D11ShaderResourceView> srv;
        ComPtr<ID3D11UnorderedAccessView> uav;
        int width = 0, height = 0;
    };
    bool make_target(Target& t, int width, int height, DXGI_FORMAT format, bool uav, bool srgb = false);
    bool ensure_targets(Renderer& renderer);
    void create_states(Renderer& renderer);
    void draw_items(ID3D11DeviceContext* c, const std::vector<GameDrawItem>& items, bool deferred);
    void fullscreen(ID3D11DeviceContext* c, ID3D11PixelShader* ps, const Target& target, float dir_x, float dir_y,
                    uint32_t combine);

    ID3D11Device* device_ = nullptr;
    int width_ = 0, height_ = 0;
    Target gbuffer_[5], hdr_, skin_diffuse_, material_diffuse_, skin_specular_, sss_temp_, bloom_[3];
    ComPtr<ID3D11Texture2D> depth_;
    ComPtr<ID3D11DepthStencilView> dsv_, dsv_read_only_;
    ComPtr<ID3D11ShaderResourceView> depth_srv_, stencil_srv_;

    ComPtr<ID3D11VertexShader> mesh_vs_, fullscreen_vs_;
    ComPtr<ID3D11InputLayout> layout_;
    ComPtr<ID3D11PixelShader> family_ps_[int(GameFamily::Count)];
    ComPtr<ID3D11ComputeShader> lighting_cs_;
    ComPtr<ID3D11PixelShader> sss_ps_, bright_ps_, blur_ps_, tonemap_ps_;

    ComPtr<ID3D11Buffer> frame_cb_, draw_cb_, pass_cb_;
    ComPtr<ID3D11RasterizerState> cull_none_, cull_back_;
    ComPtr<ID3D11DepthStencilState> ds_gbuffer_, ds_write_, ds_read_, ds_sss_;
    ComPtr<ID3D11BlendState> bs_opaque_, bs_rgb_, bs_alpha_;
    ComPtr<ID3D11SamplerState> wrap_, clamp_;
    std::shared_ptr<Texture> white_, flat_normal_;
};
