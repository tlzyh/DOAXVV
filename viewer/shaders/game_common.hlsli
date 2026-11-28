// Shared part of the game render mode, ported from the captured frame (阶段总结.md 14).
// The constant buffers mirror GameFrameConstants / GameDrawConstants in src/game_scene.h.
// Lighting runs in viewer world space, which is the character space of the capture; only the
// IBL cubes are looked up in game world space (env_dir).

cbuffer GameFrame : register(b0)
{
    row_major float4x4 view_proj;
    row_major float4x4 inv_view_proj;
    float4 camera_pos;        // xyz eye
    float4 camera_forward;    // xyz view direction
    float4 light_dir[3];      // towards the light
    float4 light_color[3];    // rgb, w specular (cloth) / translucency (skin) scale
    float4 hemi_dir;
    float4 hemi_sky;
    float4 hemi_ground;
    float4 env_rot[3];        // rows of rot_y(yaw): character space -> game world
    float4 screen;            // width, height, 1 / width, 1 / height
    float4 depth_param;       // near, far, view depth -> SSS depth (2 tan(fov / 2)), ibl strength
    float4 sss_rate;          // gRateParam
    float4 sss_blur[4];       // gBlurParam
    float4 sss_kernel[20];    // gKernel: rgb weight, w offset
    float4 bloom_offset;      // bright pass gOffset, w clamp
    float4 bloom_scale;       // bright pass gScale, w exp2 scale of the HDR alpha
    float4 bloom_weights[2];
    float4 tone;              // x exposure, y bloom scale, z blur step in source texels
    float4 tone_curve[64];    // 256 per-channel factors of the tone curve
    uint debug_view;
    uint frame_flags;         // GameFrameFlags
    uint2 frame_pad;
};

cbuffer GameDraw : register(b1)
{
    uint joint_offset;
    uint draw_flags;          // GameDrawFlags
    uint2 draw_pad;
    uint4 uv_set;             // uv index of textures 0..3
    float4 mul_color;         // gMaterialMulColor, w != 0: gray
    float4 add_color;         // gMaterialAddColor
    float4 material_param;    // gMaterialParam
    float4 material_param2;   // gMaterialParam2: x keep alpha, y flip normal
    float4 hdr_rate;          // gHDRRate
    float4 id_fresnel;        // gIDandFresnel: xy material id bytes, z reflection F0
    float4 specular;          // gSpecularColor: metal, reflectance, specular scale, gloss
    float4 ibl_diffuse;       // gIblDiffuseColor
    float4 ibl_specular;      // gIblSpecularColor
    float4 velvety_rim;       // gVelvetyRimParam
    float4 velvety;           // gVelvetyColor
    float4 rim;               // gRimColor
    float4 spec_visibility;   // gSpecularVisibilityParam
    float4 reflection_color;  // gReflectionColor
    float4 reflection_visibility;
    float4 ambient[2];        // gAmbientColor: hemisphere sky / ground times the material ambient
    float4 params[9];         // family constants, see family_params in src/game_scene.cpp
};

static const uint FRAME_NORMAL_MAPS = 1;
static const uint FRAME_TONE_CURVE = 2;
static const uint FRAME_BLOOM = 4;
static const uint FRAME_SSS = 8;

static const uint DRAW_NORMAL_MAP = 1;
static const uint DRAW_SPEC_MAP = 2;
static const uint DRAW_SPEC_ALBEDO = 4;
static const uint DRAW_REFLECTION_MAP = 8;
static const uint DRAW_DIFFUSE_ONLY = 16;
static const uint DRAW_HIGHLIGHT = 32;

static const float PI = 3.14159;
static const float3 LUMA = float3(0.29891, 0.58661, 0.11448);

TextureCube ibl_diffuse_map : register(t8);
TextureCube ibl_specular_map : register(t9);
SamplerState wrap_sampler : register(s0);
SamplerState clamp_sampler : register(s1);

float3 env_dir(float3 d)
{
    float3 g = float3(dot(env_rot[0].xyz, d), dot(env_rot[1].xyz, d), dot(env_rot[2].xyz, d));
    return float3(g.x, g.y, -g.z);
}

float3 ibl_diffuse_light(float3 n)
{
    return ibl_diffuse_map.SampleLevel(clamp_sampler, env_dir(n), 0).rgb * depth_param.w;
}

float3 ibl_specular_light(float3 r, float roughness)
{
    return ibl_specular_map.SampleLevel(clamp_sampler, env_dir(r), roughness * 6).rgb * depth_param.w;
}

float pow5(float x)
{
    float x2 = x * x;
    return x2 * x2 * x;
}

// GGX distribution and Schlick F times the visibility term of the lighting compute shader
float ggx_d(float noh, float a2)
{
    float d = noh * noh * (a2 - 1) + 1;
    return a2 / (d * d * PI + 1e-5);
}

float3 ggx_fvis(float loh, float k, float3 f0)
{
    float vis = 1 / (loh * loh * (1 - k * k) + k * k);
    return vis * (f0 + (1 - f0) * pow5(1 - loh));
}

float3 tone_factor(float3 y)
{
    uint3 i = uint3(min(y, 1) * 255);
    return float3(tone_curve[i.x >> 2][i.x & 3], tone_curve[i.y >> 2][i.y & 3], tone_curve[i.z >> 2][i.z & 3]);
}

#ifdef GAME_MESH
Texture2D tex0 : register(t0);
Texture2D tex1 : register(t1);
Texture2D tex2 : register(t2);
Texture2D tex3 : register(t3);
Texture2D suntan_map : register(t4);

struct Joint { float4 r0, r1, r2, r3; };
StructuredBuffer<Joint> joints : register(t16);

struct VSIn
{
    float3 position : POSITION;
    float3 normal : NORMAL;
    float4 tangent : TANGENT;
    float2 uv0 : TEXCOORD0;
    float2 uv1 : TEXCOORD1;
    float2 uv2 : TEXCOORD2;
    uint4 j0 : BLENDINDICES0;
    uint4 j1 : BLENDINDICES1;
    uint4 j2 : BLENDINDICES2;
    float4 w0 : BLENDWEIGHT0;
    float4 w1 : BLENDWEIGHT1;
    float4 w2 : BLENDWEIGHT2;
};

struct PSIn
{
    float4 clip : SV_Position;
    float3 world : WORLD;
    float3 normal : NORMAL;
    float4 tangent : TANGENT;
    float2 uv0 : TEXCOORD0;
    float2 uv1 : TEXCOORD1;
    float2 uv2 : TEXCOORD2;
};

float4x4 joint_matrix(uint index)
{
    Joint j = joints[joint_offset + index];
    return float4x4(j.r0, j.r1, j.r2, j.r3);
}

PSIn vs_main(VSIn v)
{
    uint idx[12] = { v.j0.x, v.j0.y, v.j0.z, v.j0.w, v.j1.x, v.j1.y, v.j1.z, v.j1.w, v.j2.x, v.j2.y, v.j2.z, v.j2.w };
    float wgt[12] = { v.w0.x, v.w0.y, v.w0.z, v.w0.w, v.w1.x, v.w1.y, v.w1.z, v.w1.w, v.w2.x, v.w2.y, v.w2.z, v.w2.w };
    float4x4 skin = (float4x4)0;
    [unroll] for (int i = 0; i < 12; ++i)
        if (wgt[i] > 0)
            skin += joint_matrix(idx[i]) * wgt[i];

    PSIn o;
    float4 world = mul(float4(v.position, 1), skin);
    o.world = world.xyz;
    o.clip = mul(world, view_proj);
    o.normal = mul(v.normal, (float3x3)skin);
    o.tangent = float4(mul(v.tangent.xyz, (float3x3)skin), v.tangent.w);
    o.uv0 = v.uv0;
    o.uv1 = v.uv1;
    o.uv2 = v.uv2;
    return o;
}

float2 pick_uv(PSIn p, uint set) { return set == 2 ? p.uv2 : set == 1 ? p.uv1 : p.uv0; }

float4 sample_slot(Texture2D t, PSIn p, uint slot) { return t.Sample(wrap_sampler, pick_uv(p, uv_set[slot])); }

// Tangent frame of the game shaders: only the normal turns around on back faces.
struct Frame { float3 n, t, b; };

Frame surface_frame(PSIn p, bool front)
{
    Frame f;
    float3 n = dot(p.normal, p.normal) > 1e-12 ? normalize(p.normal) : float3(0, 1, 0);
    float3 t = p.tangent.xyz - n * dot(n, p.tangent.xyz);
    t = dot(t, t) > 1e-12 ? normalize(t) : normalize(cross(n, abs(n.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0)));
    f.t = t;
    f.b = cross(n, t) * (p.tangent.w < 0 ? -1 : 1);
    f.n = front ? n : -n;
    return f;
}

float3 apply_normal_map(Frame f, float3 sampled)
{
    if (!(frame_flags & FRAME_NORMAL_MAPS))
        return f.n;
    float3 tn = sampled * 2 - 1;
    float3 n = tn.x * f.t + tn.y * f.b + tn.z * f.n;
    return dot(n, n) > 1e-12 ? normalize(n) : f.n;
}

float3 flip_normal(float3 n) { return material_param2.y != 0 ? -n : n; }

float3 highlight(float3 c) { return (draw_flags & DRAW_HIGHLIGHT) ? lerp(c, float3(1, 0.3, 0.1), 0.45) : c; }
#endif
