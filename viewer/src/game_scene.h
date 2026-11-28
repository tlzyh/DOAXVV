// Lighting, IBL, post-processing parameters and per-material draw setup of one RenderDoc capture,
// written by tools\rdc_scene.py into out\renderdoc\<name>\scene (阶段总结.md 14).
#pragma once

#include "character.h"
#include "json.h"
#include "renderer.h"

#include <filesystem>
#include <map>
#include <string>
#include <vector>

enum class GameFamily { Cloth, ClothFlat, WetCloth, Skin, Hair, Pbs, Count };
const char* family_name(GameFamily family);
inline bool is_deferred(GameFamily f) { return f <= GameFamily::Skin; }

enum GameDrawFlags : uint32_t {
    GameNormalMap = 1,
    GameSpecMap = 2,
    GameSpecAlbedo = 4,
    GameReflectionMap = 8,
    GameDiffuseOnly = 16,
    GameHighlight = 32,
};

enum GameFrameFlags : uint32_t { GameUseNormalMaps = 1, GameToneCurve = 2, GameBloom = 4, GameSss = 8 };

// 0 final, then the views of ps_tonemap in shaders/game_post.hlsl
enum GameDebugView : uint32_t {
    GameFinal, GameAlbedo, GameNormal, GameSpecular, GameGloss, GameMaterialId, GameNoBloom, GameSkinLight,
    GameSkinAlbedo, GameSkinSpecular, GameBloomOnly, GameStencil, GameDebugCount
};

// Mirrors cbuffer GameFrame in shaders/game_common.hlsli.
struct GameFrameConstants {
    XMFLOAT4X4 view_proj, inv_view_proj;
    XMFLOAT4 camera_pos, camera_forward;
    XMFLOAT4 light_dir[3], light_color[3];
    XMFLOAT4 hemi_dir, hemi_sky, hemi_ground;
    XMFLOAT4 env_rot[3];
    XMFLOAT4 screen;
    XMFLOAT4 depth_param;  // near, far, view depth -> SSS depth, ibl strength
    XMFLOAT4 sss_rate, sss_blur[4], sss_kernel[20];
    XMFLOAT4 bloom_offset, bloom_scale, bloom_weights[2];
    XMFLOAT4 tone;  // exposure, bloom scale, blur step
    float tone_curve[256];
    uint32_t debug_view = 0, flags = 0, pad[2] = {};
};

// Mirrors cbuffer GameDraw in shaders/game_common.hlsli; names follow the game constants.
struct GameDrawConstants {
    uint32_t joint_offset = 0, flags = 0, pad[2] = {};
    uint32_t uv_set[4] = {};
    XMFLOAT4 mul_color{1, 1, 1, 0}, add_color{0, 0, 0, 1};
    XMFLOAT4 material_param{1, 1, 0, 0}, material_param2{};
    XMFLOAT4 hdr_rate{0, 0, 1, 0};
    XMFLOAT4 id_fresnel{};
    XMFLOAT4 specular{}, ibl_diffuse{}, ibl_specular{};
    XMFLOAT4 velvety_rim{1, 0, -10000, 0}, velvety{}, rim{};
    XMFLOAT4 spec_visibility{0, 1, 0, 0}, reflection_color{}, reflection_visibility{0, 1, 0, 0};
    XMFLOAT4 ambient[2]{};
    XMFLOAT4 params[9]{};
};

// one 144-byte row of gMaterialParameterList
struct MaterialRow {
    XMFLOAT4 base_color, specular, ibl_diffuse, ibl_specular, rim, velvety, velvety_rim, ambient;
    float emissive, scatter_rate, scatter_depth_offset;
    uint32_t flags;
};
static_assert(sizeof(MaterialRow) == 144);

struct PbsType {
    std::string name;
    int id = 0;  // row of the material table, written to the G-buffer by deferred draws
    MaterialRow row{};
};

// one captured draw of a material: render state + constants
struct GamePass {
    bool blend = false, depth_write = true, cull_back = false;
    int event = 0;  // capture order, sorts the blended draws
    int stencil = 0;  // 5 skin, 4 other deferred, 0 forward
    bool srgb[4] = {true, false, false, false};
    GameDrawConstants constants;
};

struct GameMaterial {
    GameFamily family = GameFamily::Cloth;
    std::vector<GamePass> passes, original;  // original: before a PBS type was picked
    int original_pbs = -1;
    int pbs = -1;  // index into GameScene::pbs; -1: forward constants of the capture
    bool captured = false;
    bool hidden = false;  // the glb is in the capture but this material was not drawn there
    std::string source;  // where the setup came from, shown in the UI
};

struct GameLight {
    float dir[3];    // character space, towards the light
    float color[4];  // w: specular (cloth) / translucency (skin) scale
};

class GameScene {
public:
    bool load(const std::filesystem::path& dir, Renderer& renderer, std::string& error);
    bool loaded() const { return loaded_; }

    // draw setup of a glb material; materials missing from the capture get a template of
    // their family, guessed from the part role, the material name and the alpha mode
    GameMaterial& material(const Part& part, int material_index);
    void set_family(GameMaterial& m, GameFamily family, const ModelMaterial& source);
    void set_pbs(GameMaterial& m, int pbs);
    void reset_lights();
    void fill_frame(GameFrameConstants& frame) const;

    std::filesystem::path dir;
    float yaw = 0;  // game world = rot_y(yaw) * character + origin
    GameLight lights[3]{}, captured_lights[3]{};
    float hemi_dir[3]{}, hemi_sky[3]{}, hemi_ground[3]{};
    float exposure = 1, bloom_scale = 2, ibl_strength = 1;
    std::vector<PbsType> pbs;

    ComPtr<ID3D11ShaderResourceView> material_table, skin_table, ibl_diffuse, ibl_specular;
    std::shared_ptr<Texture> suntan;

private:
    GameMaterial parse_material(const Json& m) const;
    GamePass parse_pass(const Json& p, GameFamily family, uint32_t flags) const;

    bool loaded_ = false;
    float tone_curve_[256]{};
    XMFLOAT4 bloom_offset_{}, bloom_scale_{}, sss_rate_{}, sss_blur_[4]{}, sss_kernel_[20]{};
    float bloom_weights_[8]{}, bloom_step_ = 1;
    std::map<std::string, std::map<std::string, GameMaterial>> captured_;  // glb -> material name
    GameMaterial templates_[int(GameFamily::Count)];
    GameMaterial hair_blended_;  // hair template without the opaque pass
    std::map<std::string, GameMaterial> cache_;  // glb|material
};
