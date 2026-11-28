// Direct3D 11 renderer. Shaders are HLSL files in viewer/shaders/, compiled at run time
// and reloaded when they change, so captured game shaders can be dropped in later.
#pragma once

#include <d3d11.h>
#include <dxgi1_2.h>
#include <DirectXMath.h>
#include <wrl/client.h>

#include <filesystem>
#include <memory>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
using DirectX::XMFLOAT4;
using DirectX::XMFLOAT4X4;

// Up to 12 bone influences, as the TMC vertex formats carry 3 sets of 4.
struct Vertex {
    float position[3];
    float normal[3];
    float tangent[4];
    float uv0[2];
    float uv1[2];
    uint8_t joints[12];
    float weights[12];
};

struct Texture {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<ID3D11ShaderResourceView> linear;  // UNORM view
    ComPtr<ID3D11ShaderResourceView> srgb;    // UNORM_SRGB view, for color maps
    int width = 0, height = 0;
};

// Mirrors cbuffer Frame in shaders/model.hlsl (row-vector matrices, 16-byte rows).
struct FrameConstants {
    XMFLOAT4X4 view_proj;
    XMFLOAT4 camera_pos;    // xyz
    XMFLOAT4 light_dir;     // xyz towards the light, w intensity
    XMFLOAT4 light_color;   // rgb, w ambient strength
    XMFLOAT4 sky_color;     // rgb, w 1 = use normal maps
    XMFLOAT4 ground_color;  // rgb, w exposure
    int debug_mode = 0;     // 0 lit, 1 base color, 2 normal, 3 uv0, 4 texture slot, 5 vertex normal
    int debug_slot = 0;
    int debug_channel = 0;  // 0 rgb, 1 r, 2 g, 3 b, 4 a
    int pad = 0;
};

enum DrawFlags : uint32_t { HasColor = 1, HasNormal = 2, HasSlot = 4, Highlight = 8 };

// Mirrors cbuffer Draw in shaders/model.hlsl.
struct DrawConstants {
    uint32_t joint_offset = 0;
    uint32_t flags = 0;
    uint32_t alpha_mode = 0;  // 0 opaque, 1 mask, 2 blend
    float alpha_cutoff = 0.5f;
    uint32_t color_uv = 0, normal_uv = 0, slot_uv = 0, pad = 0;
};

struct DrawItem {
    ID3D11Buffer* vertices = nullptr;
    ID3D11Buffer* indices = nullptr;
    DXGI_FORMAT index_format = DXGI_FORMAT_R32_UINT;
    uint32_t index_count = 0;
    const Texture* color = nullptr;
    const Texture* normal = nullptr;
    const Texture* slot = nullptr;  // texture of the debug slot
    DrawConstants constants;
    float depth = 0;  // view depth of the primitive centre, for sorting blended draws
};

class Renderer {
public:
    bool init(void* hwnd, int width, int height, std::string& error);
    void shutdown();
    void resize(int width, int height);

    // returns false and fills log on a compile error (the previous shaders stay active)
    bool reload_shaders(std::string& log);
    // reloads when a file in the shader folder changed; true if it tried
    bool poll_shaders(std::string& log);
    std::filesystem::path shader_dir;

    std::shared_ptr<Texture> create_texture(const void* rgba, int width, int height);
    ComPtr<ID3D11Buffer> create_buffer(const void* data, size_t bytes, UINT bind);

    void upload_joints(const std::vector<XMFLOAT4X4>& matrices);
    void begin_frame(const float clear[4]);
    void draw_scene(std::vector<DrawItem>& items, const FrameConstants& frame, bool wireframe);
    void begin_ui();
    void present(bool vsync);
    // call before present; writes a BMP
    bool save_backbuffer(const std::filesystem::path& path);

    // draws one texture channel into an offscreen target for ImGui::Image
    ID3D11ShaderResourceView* preview(const Texture* texture, int channel, bool srgb);

    ID3D11Device* device() const { return device_.Get(); }
    ID3D11DeviceContext* context() const { return context_.Get(); }
    int width() const { return width_; }
    int height() const { return height_; }

private:
    bool create_targets(std::string& error);
    ComPtr<ID3DBlob> compile(const std::filesystem::path& file, const char* entry, const char* target,
                             std::string& log);

    ComPtr<ID3D11Device> device_;
    ComPtr<ID3D11DeviceContext> context_;
    ComPtr<IDXGISwapChain1> swap_chain_;
    ComPtr<ID3D11RenderTargetView> rtv_srgb_, rtv_ui_;
    ComPtr<ID3D11DepthStencilView> dsv_;
    ComPtr<ID3D11VertexShader> vs_;
    ComPtr<ID3D11PixelShader> ps_;
    ComPtr<ID3D11InputLayout> layout_;
    ComPtr<ID3D11VertexShader> preview_vs_;
    ComPtr<ID3D11PixelShader> preview_ps_;
    ComPtr<ID3D11Buffer> frame_cb_, draw_cb_, preview_cb_;
    ComPtr<ID3D11Buffer> joints_;
    ComPtr<ID3D11ShaderResourceView> joints_srv_;
    size_t joint_capacity_ = 0;
    ComPtr<ID3D11SamplerState> sampler_;
    ComPtr<ID3D11RasterizerState> solid_, wire_;
    ComPtr<ID3D11DepthStencilState> depth_write_, depth_read_;
    ComPtr<ID3D11BlendState> opaque_, alpha_;
    ComPtr<ID3D11Texture2D> preview_tex_;
    ComPtr<ID3D11RenderTargetView> preview_rtv_;
    ComPtr<ID3D11ShaderResourceView> preview_srv_;
    int width_ = 0, height_ = 0;
    std::filesystem::file_time_type shader_stamp_{};
};
