// Skinned model shader. Matrices are row-vector (mul(v, M)), matching the C++ side.
// Edit and save: the viewer recompiles on change (or press F5). The constant buffers
// mirror FrameConstants / DrawConstants in src/renderer.h.

cbuffer Frame : register(b0)
{
    row_major float4x4 view_proj;
    float4 camera_pos;
    float4 light_dir;      // xyz towards the light, w intensity
    float4 light_color;    // rgb, w ambient strength
    float4 sky_color;      // rgb, w 1 = use normal maps
    float4 ground_color;   // rgb, w exposure
    int debug_mode;        // 0 lit, 1 base color, 2 normal, 3 uv0, 4 texture slot, 5 vertex normal
    int debug_slot;
    int debug_channel;     // 0 rgb, 1 r, 2 g, 3 b, 4 a
    int frame_pad;
};

cbuffer Draw : register(b1)
{
    uint joint_offset;
    uint flags;            // 1 color, 2 normal map, 4 debug slot texture, 8 highlight
    uint alpha_mode;       // 0 opaque, 1 mask, 2 blend
    float alpha_cutoff;
    uint color_uv;
    uint normal_uv;
    uint slot_uv;
    uint draw_pad;
};

struct Joint { float4 r0, r1, r2, r3; };
StructuredBuffer<Joint> joints : register(t8);

Texture2D color_map : register(t0);
Texture2D normal_map : register(t1);
Texture2D slot_map : register(t2);
SamplerState linear_sampler : register(s0);

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

// The target is sRGB: data textures (and alpha) are shown with their stored byte values.
float4 channel_view(float4 c)
{
    float3 v = c.rgb;
    if (debug_channel == 1) v = c.rrr;
    if (debug_channel == 2) v = c.ggg;
    if (debug_channel == 3) v = c.bbb;
    if (debug_channel == 4) v = c.aaa;
    if (debug_slot != 0 || debug_channel == 4)
        v = pow(saturate(v), 2.2);
    return float4(v, 1);
}

float4 ps_main(PSIn p, bool front : SV_IsFrontFace) : SV_Target
{
    float4 base = (flags & 1) ? color_map.Sample(linear_sampler, pick_uv(p, color_uv)) : float4(0.8, 0.8, 0.8, 1);
    // skin color alpha is a shading mask, not opacity (阶段总结.md 8); only mask / blend use it
    float alpha = alpha_mode == 0 ? 1 : base.a;
    if (alpha_mode == 1)
        clip(alpha - alpha_cutoff);

    float3 n = dot(p.normal, p.normal) > 1e-12 ? normalize(p.normal) : float3(0, 1, 0);
    if (!front)
        n = -n;
    float3 vertex_normal = n;
    float3 t_raw = p.tangent.xyz - n * dot(n, p.tangent.xyz);
    if ((flags & 2) && sky_color.w > 0.5 && dot(t_raw, t_raw) > 1e-12)
    {
        float3 t = normalize(t_raw);
        float3 b = cross(n, t) * (p.tangent.w < 0 ? -1 : 1);
        float3 tn = normal_map.Sample(linear_sampler, pick_uv(p, normal_uv)).xyz * 2 - 1;
        n = normalize(tn.x * t + tn.y * b + tn.z * n);
    }

    if (debug_mode == 1) return float4(base.rgb, 1);
    if (debug_mode == 2) return float4(n * 0.5 + 0.5, 1);
    if (debug_mode == 3) return float4(frac(p.uv0), 0, 1);
    if (debug_mode == 4) return (flags & 4) ? channel_view(slot_map.Sample(linear_sampler, pick_uv(p, slot_uv))) : float4(0, 0, 0, 1);
    if (debug_mode == 5) return float4(vertex_normal * 0.5 + 0.5, 1);

    float3 l = normalize(light_dir.xyz);
    float3 v = normalize(camera_pos.xyz - p.world);
    float ndl = saturate(dot(n, l));
    float3 hemi = lerp(ground_color.rgb, sky_color.rgb, n.y * 0.5 + 0.5) * light_color.w;
    float spec = pow(saturate(dot(n, normalize(l + v))), 48) * 0.15;
    float3 lit = base.rgb * (hemi + light_color.rgb * light_dir.w * ndl) + spec * light_color.rgb * light_dir.w;
    lit *= ground_color.w;
    if (flags & 8)
        lit = lerp(lit, float3(1, 0.3, 0.1), 0.45);
    return float4(lit, alpha);
}
