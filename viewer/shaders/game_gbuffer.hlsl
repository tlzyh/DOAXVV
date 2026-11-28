// G-buffer pixel shaders of the deferred character materials:
// ps_cloth = ps_55b76df67077, ps_cloth_flat = ps_d0fb033099aa, ps_wet_cloth = ps_524852116c9f,
// ps_skin = ps_c89ae5936261. The game writes view-space normals, these write world space.
// RT0 albedo (sRGB), RT1 normal, RT2 specular mask + gloss, RT3 material id, RT4 sweat normal.
#define GAME_MESH
#include "game_common.hlsli"

struct GBuffer
{
    float4 albedo : SV_Target0;
    float4 normal : SV_Target1;
    float4 specular : SV_Target2;
    float4 id : SV_Target3;
    float4 sweat : SV_Target4;
};

GBuffer gbuffer(float3 albedo, float3 n, float4 spec)
{
    GBuffer o;
    o.albedo = float4(highlight(albedo), 1);
    o.normal = float4(flip_normal(n), 1);
    o.specular = spec;
    o.id = float4(id_fresnel.xyw, mul_color.w);
    o.sweat = 0;
    return o;
}

float3 material_color(float3 c) { return c * mul_color.rgb + add_color.rgb; }

GBuffer ps_cloth(PSIn p, bool front : SV_IsFrontFace)
{
    Frame f = surface_frame(p, front);
    float3 albedo = material_color(sample_slot(tex0, p, 0).rgb);
    float3 n = apply_normal_map(f, sample_slot(tex1, p, 1).xyz);
    return gbuffer(albedo, n, sample_slot(tex2, p, 2));
}

GBuffer ps_cloth_flat(PSIn p, bool front : SV_IsFrontFace)
{
    Frame f = surface_frame(p, front);
    float3 albedo = material_color(sample_slot(tex0, p, 0).rgb);
    return gbuffer(albedo, f.n, sample_slot(tex1, p, 1));
}

// params[0] = gWetClothAbsParameter: x wet, y dry weight, zw normal slice of the 3D normal map
// (the glb holds only its first slice)
GBuffer ps_wet_cloth(PSIn p, bool front : SV_IsFrontFace)
{
    Frame f = surface_frame(p, front);
    float4 wet = params[0];
    float4 dry_tex = sample_slot(tex0, p, 0), wet_tex = sample_slot(tex1, p, 1);
    float3 albedo = material_color(wet_tex.rgb * wet.x + dry_tex.rgb * wet.y);
    float3 n = apply_normal_map(f, sample_slot(tex2, p, 2).xyz);
    float4 spec = float4(wet_tex.aaa, 1) * wet.x + float4(dry_tex.aaa, 1) * wet.y;
    return gbuffer(albedo, n, spec);
}

// params: 0 gSkinSweatParameter, 1 gSkinSweatDropSpecularColor, 3 gSkinSweatMaterialParameter,
// 4 gSkinSuntanColor, 8 gSkinFlushParam. t4 is the suntan mask, read with the uv of slot 3.
GBuffer ps_skin(PSIn p, bool front : SV_IsFrontFace)
{
    Frame f = surface_frame(p, front);
    float4 sweat = params[0], drop = params[1], smat = params[3], tan_color = params[4], flush = params[8];
    float2 uv3 = pick_uv(p, uv_set[3]);
    float tan = suntan_map.Sample(wrap_sampler, uv3).x * smat.z;
    float4 color = sample_slot(tex0, p, 0);
    float4 sweat_mask = sample_slot(tex1, p, 1);
    float4 detail = tex3.Sample(wrap_sampler, uv3);

    float3 c = color.rgb * (1 - (1 - sweat_mask.rgb) * (sweat.x * drop.z));
    c = pow(max(c * (1 - tan_color.rgb * tan), 0), 1 + 0.5 * tan_color.rgb * tan);
    c *= 1 + detail.a * flush.rgb * smat.w;
    float3 albedo = material_color(c);

    float3 n = apply_normal_map(f, sample_slot(tex2, p, 2).xyz);
    GBuffer o = gbuffer(albedo, n, float4(detail.rgb, color.a));
    o.sweat = float4(n, sweat_mask.a * sweat.x);
    return o;
}
