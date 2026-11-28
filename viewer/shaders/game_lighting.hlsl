// Deferred lighting of the character pixels, ported from cs_b848e33994e7 (阶段总结.md 14):
// the three character lights, hemisphere 0, IBL and the material parameter table.
// Left out: shadows (factor 1), point and spot lights, SSAO, the environment branch and the
// sweat drop wet light (its direction is in game view space).
// stencil & 15 == 5: skin, written to the three skin buffers for the SSS passes
// stencil & 12 == 4: other character materials, written to the HDR target
#include "game_common.hlsli"

struct MaterialRow
{
    float4 base_color;
    float4 specular;        // metal, reflectance, specular scale, gloss
    float4 ibl_diffuse;
    float4 ibl_specular;
    float4 rim;
    float4 velvety;
    float4 velvety_rim;     // NoL scale, NoL bias, rim NoV scale, rim NoV bias
    float4 ambient;
    float emissive;
    float scatter_rate;
    float scatter_depth_offset;
    uint flags;
};

Texture2D gb0 : register(t0);
Texture2D gb1 : register(t1);
Texture2D gb2 : register(t2);
Texture2D gb3 : register(t3);
Texture2D gb4 : register(t4);
Texture2D<float> depth_tex : register(t5);
Texture2D<uint2> stencil_tex : register(t6);
StructuredBuffer<MaterialRow> materials : register(t7);
ByteAddressBuffer skin_rows : register(t10);  // 112-byte rows, read unaligned like the game

RWTexture2D<float4> hdr_out : register(u0);
RWTexture2D<float4> skin_diffuse_out : register(u1);
RWTexture2D<float4> material_diffuse_out : register(u2);
RWTexture2D<float4> skin_specular_out : register(u3);

float skin_f(uint row, uint offset) { return asfloat(skin_rows.Load(row * 112 + offset)); }

float3 hemisphere(MaterialRow m, float3 n)
{
    return m.ambient.rgb * (hemi_sky.rgb + dot(n, hemi_dir.xyz) * hemi_ground.rgb);
}

// v points from the eye to the pixel, as in the game
float4 shade_character(MaterialRow m, float4 g0, float3 n, float4 g2, float4 g3, float3 v)
{
    float3 albedo = g0.rgb * (1 + m.emissive);
    float metal = m.specular.x, refl = m.specular.y;
    float3 f0 = saturate(albedo * metal + 0.16 * refl * refl);
    albedo *= 1 - metal;
    float ndv = dot(n, -v);
    float rim_vis = saturate(abs(ndv) * m.velvety_rim.z + m.velvety_rim.w);
    float gloss = m.specular.w * g2.w;
    float rough = 1 - gloss;
    float a = rough * rough, a2 = a * a, k = a * 0.5;

    float3 diffuse = 0, spec = 0;
    [unroll] for (uint i = 0; i < 3; ++i)
    {
        float3 l = light_dir[i].xyz, c = light_color[i].rgb;
        float nol = dot(n, l), snol = saturate(nol);
        if (nol > 0)
        {
            diffuse += snol / PI * c;
            float3 h = normalize(l - v);
            float loh = saturate(dot(l, h)), noh = saturate(dot(h, n));
            spec = max(spec + ggx_fvis(loh, k, f0) * (m.specular.z * light_color[i].w * snol * ggx_d(noh, a2)) * c, 0);
        }
        diffuse += (saturate(nol * m.velvety_rim.x + m.velvety_rim.y) - snol) * c * m.velvety.rgb;
        diffuse += saturate((1 - nol) * 0.5) * saturate(dot(l, v)) * rim_vis * c * m.rim.rgb;
    }

    float fr = saturate(gloss + refl);
    float fc = pow5(1 - saturate(ndv));
    float3 ibl_s = ibl_specular_light(reflect(v, n), rough) * (f0 + fc * (fr - f0)) * m.ibl_specular.rgb;
    float3 diff_total = diffuse * m.base_color.rgb + ibl_diffuse_light(n) * m.ibl_diffuse.rgb;
    float3 spec_total = spec * m.base_color.rgb + ibl_s;
    float3 color = (diff_total + hemisphere(m, n)) * albedo + g2.rgb * spec_total;
    if (g3.w != 0)
        color = dot(color, LUMA);
    return float4(color, m.emissive);
}

struct SkinResult
{
    float3 skin_diffuse;      // lit diffuse, blurred by the SSS passes
    float3 material_diffuse;  // albedo part applied after the blur
    float3 specular;
};

SkinResult shade_skin(MaterialRow m, uint row, float4 g0, float3 n, float4 g2, float4 g3, float4 g4, uint stencil,
                      float3 v)
{
    float2 mp = float2(skin_f(row, 0), skin_f(row, 4));
    float4 t = float4(skin_f(row, 16), skin_f(row, 20), skin_f(row, 24), skin_f(row, 28));

    float3 albedo = g0.rgb * (1 + m.emissive);
    float metal = m.specular.x, refl = m.specular.y, gloss = m.specular.w;
    float3 f0 = saturate(albedo * metal + 0.16 * refl * refl);
    albedo *= 1 - metal;
    float rough = 1 - gloss;
    float a = rough * rough, a2 = a * a, k = a * 0.5;

    float3 diffuse = 0, spec = 0;
    [unroll] for (uint i = 0; i < 3; ++i)
    {
        float3 l = light_dir[i].xyz, c = light_color[i].rgb;
        float nol = dot(n, l), snol = saturate(nol);
        if (nol > 0)
        {
            diffuse += snol / PI * c;
            float3 h = normalize(l - v);
            float loh = saturate(dot(l, h)), noh = saturate(dot(h, n));
            spec = max(spec + ggx_fvis(loh, k, f0) * (m.specular.z * snol * ggx_d(noh, a2)) * c, 0);
        }
        diffuse += (saturate(nol * m.velvety_rim.x + m.velvety_rim.y) - snol) * c * m.velvety.rgb;
        float back = exp2(saturate(dot(v, l + n * t.x)) * t.y - t.y + 1e-4);
        diffuse += c * g2.y * (back * t.z * light_color[i].w + t.w);
    }

    float fr = saturate(refl + gloss);
    float fc = pow5(1 - saturate(dot(-v, n)));
    float3 ibl_s = ibl_specular_light(reflect(v, n), rough) * (f0 + fc * (fr - f0)) * m.ibl_specular.rgb;
    float3 lit = ibl_diffuse_light(n) * m.ibl_diffuse.rgb + diffuse * m.base_color.rgb;
    float3 light_diffuse = (lit + hemisphere(m, n)) * (1 + mp.y * (g2.z - 1));
    float3 spec_total = spec * m.base_color.rgb + ibl_s;

    // sweat drops: second specular layer on the RT4 normal, weighted by its w
    float wet = g4.w, sweat_metal = 0;
    float3 sweat = 0;
    if (wet > 0)
    {
        float3 n2 = normalize(g4.xyz);
        sweat_metal = min(skin_f(row, 32), 1);
        float rs = min(skin_f(row, 36), 1), gs = min(skin_f(row, 44), 1);
        float f0s = 0.16 * rs * rs + sweat_metal;
        float r2 = 1 - gs, a2s = r2 * r2 * r2 * r2, ks = r2 * r2 * 0.5;
        float3 sum = 0;
        [unroll] for (uint j = 0; j < 3; ++j)
        {
            float3 l = light_dir[j].xyz;
            float nol = dot(n2, l);
            if (nol > 0)
            {
                float3 h = normalize(l - v);
                float loh = saturate(dot(l, h)), noh = saturate(dot(h, n2));
                sum += ggx_fvis(loh, ks, f0s) * (skin_f(row, 60) * saturate(nol) * ggx_d(noh, a2s)) * light_color[j].rgb;
            }
        }
        float fr2 = saturate(rs + gs);
        float fc2 = pow5(1 - saturate(dot(-v, n2)));
        float3 ibl_color = float3(skin_f(row, 48), skin_f(row, 52), skin_f(row, 56));
        sweat = (ibl_specular_light(reflect(v, n2), r2) * (f0s + fc2 * (fr2 - f0s)) * ibl_color + sum) * wet;
    }

    SkinResult o;
    o.specular = spec_total * (g2.z * g2.w) + sweat;
    float s = (stencil & 64) ? saturate(1 - g2.x) : 0;
    s = saturate(s + mp.x);
    float3 base = albedo * (1 - sweat_metal * wet) + 1e-5;
    o.material_diffuse = pow(base, s);
    o.skin_diffuse = pow(base, 1 - s) * light_diffuse;
    if (g3.w != 0)
    {
        o.material_diffuse = dot(o.material_diffuse, LUMA);
        o.skin_diffuse = dot(o.skin_diffuse, LUMA);
        o.specular = dot(o.specular, LUMA);
    }
    return o;
}

[numthreads(8, 8, 1)]
void cs_main(uint3 id : SV_DispatchThreadID)
{
    if (any(id.xy >= uint2(screen.xy)))
        return;
    int3 px = int3(id.xy, 0);
    uint stencil = stencil_tex.Load(px).g;
    if ((stencil & 12) == 0)
        return;
    float depth = depth_tex.Load(px);
    float2 ndc = float2((id.x + 0.5) * screen.z * 2 - 1, 1 - (id.y + 0.5) * screen.w * 2);
    float4 world = mul(float4(ndc, depth, 1), inv_view_proj);
    float3 v = normalize(world.xyz / world.w - camera_pos.xyz);

    float4 g0 = gb0.Load(px), g1 = gb1.Load(px), g2 = gb2.Load(px), g3 = gb3.Load(px);
    float3 n = normalize(g1.xyz);
    uint material = uint(round(g3.x * 255)) | (uint(round(g3.y * 255)) << 8);
    MaterialRow m = materials[min(material, 4095u)];

    if ((stencil & 15) == 5)
    {
        uint row = (uint(round(g3.z * 255)) & 7) - 1;
        SkinResult s = shade_skin(m, min(row, 3u), g0, n, g2, g3, gb4.Load(px), stencil, v);
        skin_diffuse_out[id.xy] = float4(s.skin_diffuse, 1);
        material_diffuse_out[id.xy] = float4(s.material_diffuse, 1);
        skin_specular_out[id.xy] = float4(s.specular, 1);
        // replaced by the SSS passes when they run
        hdr_out[id.xy] = float4(s.skin_diffuse * s.material_diffuse + s.specular, m.emissive);
    }
    else if ((stencil & 12) == 4)
    {
        hdr_out[id.xy] = shade_character(m, g0, n, g2, g3, v);
    }
}
