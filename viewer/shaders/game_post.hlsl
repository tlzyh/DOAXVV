// Full-screen passes of the game render mode (阶段总结.md 14):
// ps_sss = ps_ab7c1e63266a (horizontal, then vertical + combine where stencil & 15 == 5),
// ps_bright = ps_54500588f263, ps_blur = ps_fbd21ffdc07a, ps_tonemap = ps_4f9e3239f4bf
// without the color grading LUT.
#include "game_common.hlsli"

cbuffer GamePass : register(b2)
{
    float4 pass_dir;      // xy direction of the blur, in uv per source texel for ps_blur
    uint pass_combine;    // ps_sss: 1 = vertical pass, writes the lit skin
    uint3 pass_pad;
};

Texture2D src : register(t0);
Texture2D material_diffuse : register(t1);
Texture2D skin_specular : register(t2);
Texture2D gb3 : register(t3);
Texture2D<float> depth_tex : register(t4);
Texture2D bloom_tex : register(t5);
Texture2D gb0 : register(t6);
Texture2D gb1 : register(t7);
Texture2D gb2 : register(t10);
Texture2D<uint2> stencil_tex : register(t11);
Texture2D skin_diffuse : register(t12);

struct VSOut
{
    float4 pos : SV_Position;
    float2 uv : TEXCOORD0;
};

VSOut vs_fullscreen(uint id : SV_VertexID)
{
    VSOut o;
    o.uv = float2((id << 1) & 2, id & 2);
    o.pos = float4(o.uv * float2(2, -2) + float2(-1, 1), 0, 1);
    return o;
}

float view_depth(float d)
{
    float n = depth_param.x, f = depth_param.y;
    return n * f / (f - d * (f - n));
}

int skin_mask(float2 uv)
{
    return int(round(gb3.SampleLevel(clamp_sampler, uv, 0).z * 255));
}

float4 ps_sss(VSOut i) : SV_Target
{
    int2 px = int2(i.pos.xy);
    int mask = int(round(gb3.Load(int3(px, 0)).z * 255));
    float4 center = src.Load(int3(px, 0));
    float3 blurred = center.rgb;
    if (mask > 0 && (frame_flags & FRAME_SSS))
    {
        float lin = view_depth(depth_tex.Load(int3(px, 0))) * depth_param.z;
        float scale = lin <= sss_rate.z ? 0.012 : lin >= sss_rate.w ? 0 : lerp(0.012, 0, (lin - sss_rate.z) / (sss_rate.w - sss_rate.z));
        float2 step = scale * sss_blur[min(mask - 1, 3)].z * pass_dir.xy / 3;
        float3 sum = 0, weight = 0;
        [loop] for (int k = 0; k < 20; ++k)
        {
            float2 uv = i.uv + step * sss_kernel[k].w;
            if (skin_mask(uv) != mask)
                continue;
            sum += src.SampleLevel(clamp_sampler, uv, 0).rgb * sss_kernel[k].rgb;
            weight += sss_kernel[k].rgb;
        }
        blurred = sum / max(weight, 1e-4);
    }
    if (pass_combine == 0)
        return float4(blurred, 1);
    float4 m = material_diffuse.Load(int3(px, 0));
    return float4(blurred * m.rgb + skin_specular.Load(int3(px, 0)).rgb, 0);
}

float4 ps_bright(VSOut i) : SV_Target
{
    float4 c = src.SampleLevel(clamp_sampler, i.uv, 0);
    float3 rgb = c.rgb * exp2(c.a * bloom_scale.w);
    return float4(clamp((rgb + bloom_offset.rgb) * bloom_scale.rgb, 0, bloom_offset.w), 1);
}

float4 ps_blur(VSOut i) : SV_Target
{
    float3 sum = 0;
    [unroll] for (int k = 0; k < 8; ++k)
    {
        float2 offset = pass_dir.xy * ((2 * k + 1) * tone.z);
        float w = bloom_weights[k >> 2][k & 3];
        sum += (src.SampleLevel(clamp_sampler, i.uv + offset, 0).rgb + src.SampleLevel(clamp_sampler, i.uv - offset, 0).rgb) * w;
    }
    return float4(sum, 1);
}

float3 hejl(float3 c)
{
    float3 x = max(c * tone.x - 0.004, 0);
    float3 y = x * (6.2 * x + 0.5) / (x * (6.2 * x + 1.7) + 0.06);
    if (frame_flags & FRAME_TONE_CURVE)
        y *= tone_factor(y);
    return y;
}

float3 id_color(uint id)
{
    uint h = id * 2654435761u;
    return float3((h >> 8) & 255, (h >> 16) & 255, (h >> 24) & 255) / 255;
}

// debug views (GameDebugView in src/game_scene.h); the target is a UNORM backbuffer, so linear
// values are shown with a 2.2 gamma
float4 ps_tonemap(VSOut i) : SV_Target
{
    int3 px = int3(i.pos.xy, 0);
    float4 hdr = src.Load(px);
    float3 bloom = (frame_flags & FRAME_BLOOM) ? bloom_tex.SampleLevel(clamp_sampler, i.uv, 0).rgb : 0;
    float3 g = 1 / 2.2;
    switch (debug_view)
    {
        case 1: return float4(pow(gb0.Load(px).rgb, g), 1);
        case 2: return float4(gb1.Load(px).xyz * 0.5 + 0.5, 1);
        case 3: return float4(gb2.Load(px).rgb, 1);
        case 4: return float4(gb2.Load(px).aaa, 1);
        case 5:
        {
            float4 id = gb3.Load(px);
            uint material = uint(round(id.x * 255)) | (uint(round(id.y * 255)) << 8);
            return float4((stencil_tex.Load(px).g & 12) ? id_color(material) : 0, 1);
        }
        case 6: return float4(hejl(hdr.rgb), 1);
        case 7: return float4(hejl(skin_diffuse.Load(px).rgb), 1);
        case 8: return float4(pow(saturate(material_diffuse.Load(px).rgb), g), 1);
        case 9: return float4(hejl(skin_specular.Load(px).rgb), 1);
        case 10: return float4(hejl(bloom * tone.y), 1);
        case 11:
        {
            uint s = stencil_tex.Load(px).g;
            return float4((s & 15) == 5 ? float3(1, 0.5, 0.4) : (s & 12) == 4 ? float3(0.3, 0.6, 1) : 0, 1);
        }
    }
    return float4(hejl(hdr.rgb + bloom * tone.y), 1);
}
