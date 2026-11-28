// Forward character materials drawn after the deferred lighting (阶段总结.md 14).
// ps_pbs follows the template ps_073e8cdcb837; draw_flags select the captured variants
// (f9b7 eyes: specular from albedo + reflection map, 6156 / b387 / e368: vertex normal or
// diffuse only). ps_hair = ps_b4bf46237b69. Shadows, fog and light scattering are left out.
#define GAME_MESH
#include "game_common.hlsli"

float alpha_of(PSIn p, float a)
{
    if (material_param.z != 0)
    {
        // alpha to coverage style sharpening of the game shaders
        float2 dx = ddx_coarse(p.uv0), dy = ddy_coarse(p.uv0);
        float scale = max(0.5 * log2(max(dot(dx, dx), dot(dy, dy))), 0) * 0.25 + 1;
        float sa = a * scale;
        a = (sa - material_param.w) / max(abs(ddx_coarse(sa)) + abs(ddy_coarse(sa)), 1e-4) + 0.5;
    }
    clip(a - hdr_rate.x);
    return a;
}

float3 hemisphere(float3 n) { return ambient[0].rgb + dot(n, hemi_dir.xyz) * ambient[1].rgb; }

float4 finish(float3 color, float a)
{
    color = max(highlight(color), 0);
    if (mul_color.w != 0)
        color = dot(color, LUMA);
    return float4(color, a);
}

float4 ps_pbs(PSIn p, bool front : SV_IsFrontFace) : SV_Target
{
    Frame f = surface_frame(p, front);
    float4 texel = sample_slot(tex0, p, 0);
    float a = alpha_of(p, texel.a);
    float3 color = texel.rgb * mul_color.rgb + add_color.rgb;
    a = saturate(a + hdr_rate.z);
    float3 albedo = color * (1 + hdr_rate.y);

    float3 n = (draw_flags & DRAW_NORMAL_MAP) ? apply_normal_map(f, sample_slot(tex1, p, 1).xyz) : f.n;
    n = flip_normal(n);
    float3 v = normalize(p.world - camera_pos.xyz);
    float3 r = reflect(v, n);

    float3 mask = 1;
    float gloss_mask = 1;
    if (draw_flags & DRAW_SPEC_MAP)
    {
        float4 s = sample_slot(tex2, p, 2);
        mask = s.rgb;
        gloss_mask = s.a;
    }
    else if (draw_flags & DRAW_SPEC_ALBEDO)
        mask = color * spec_visibility.x + spec_visibility.y;

    float metal = specular.x, refl = specular.y;
    float3 f0 = saturate(albedo * metal + 0.16 * refl * refl);
    albedo *= 1 - metal;
    float ndv = dot(n, -v);
    float rim_vis = saturate(abs(ndv) * velvety_rim.z + velvety_rim.w);
    float gloss = specular.w * gloss_mask;
    float rough = 1 - gloss;
    float a1 = rough * rough, a2 = a1 * a1, k = a1 * 0.5;
    bool lit_spec = !(draw_flags & DRAW_DIFFUSE_ONLY);

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
            spec = max(spec + ggx_fvis(loh, k, f0) * (specular.z * light_color[i].w * snol * ggx_d(noh, a2)) * c, 0);
        }
        diffuse += (saturate(nol * velvety_rim.x + velvety_rim.y) - snol) * c * velvety.rgb;
        diffuse += saturate((1 - nol) * 0.5) * saturate(dot(l, v)) * rim_vis * c * rim.rgb;
    }

    float3 diff_total = hemisphere(n) + diffuse + ibl_diffuse_light(n) * ibl_diffuse.rgb;
    float3 spec_total = 0;
    if (lit_spec)
    {
        float fr = saturate(gloss + refl);
        float fc = pow5(1 - saturate(ndv));
        spec_total = ibl_specular_light(r, rough) * (f0 + fc * (fr - f0)) * ibl_specular.rgb + spec;
    }
    float3 out_color = albedo * diff_total + mask * spec_total;
    float glow = 0;
    if (draw_flags & DRAW_REFLECTION_MAP)
    {
        float fresnel = saturate(pow(1 - saturate(dot(n, r)), 4) * (1 - id_fresnel.z) + id_fresnel.z);
        float4 reflection = sample_slot(tex1, p, 1) * reflection_color * fresnel;
        out_color += reflection.rgb * (mask * reflection_visibility.x + reflection_visibility.y);
        glow = reflection.w;
    }
    float out_alpha = material_param2.x != 0 ? a : hdr_rate.w * a + glow + hdr_rate.y;
    return finish(out_color, out_alpha);
}

// params: 0 gHairParameter (shift scale, secondary shift, primary / secondary exponent scale),
// 1 primary color, 2 secondary color, 3 gHairExtraParameter (z: minimum NoL of the highlight)
float4 ps_hair(PSIn p, bool front : SV_IsFrontFace) : SV_Target
{
    Frame f = surface_frame(p, front);
    float4 texel = sample_slot(tex0, p, 0);
    float a = alpha_of(p, texel.a);
    a = saturate(a + hdr_rate.z);
    float3 albedo = (texel.rgb * mul_color.rgb + add_color.rgb) * (1 + hdr_rate.y);
    float3 n = flip_normal(apply_normal_map(f, sample_slot(tex1, p, 1).xyz));
    float4 s = sample_slot(tex2, p, 2);
    float4 hair = params[0];

    float3 to_pixel = p.world - camera_pos.xyz;
    float dist = length(to_pixel);
    float3 v = to_pixel / dist;
    float rim_vis = saturate(abs(dot(n, -v)) * velvety_rim.z + velvety_rim.w);
    albedo *= 1 - specular.x;

    // shifted tangent and two eye positions moved along y give the two highlight bands
    float3 t = normalize(f.b - 2 * s.y * n);
    float shift = (s.z - 0.5) * 2 * hair.x;
    float3 eye1 = camera_pos.xyz + float3(0, dist * shift, 0);
    float3 eye2 = eye1 + float3(0, dist * hair.y, 0);
    float3 l0 = 0.6 * light_dir[0].xyz;
    float3 h1 = normalize(normalize(p.world - eye1) - l0);
    float3 h2 = normalize(normalize(p.world - eye2) - l0);
    float d1 = dot(h1, t), d2 = dot(h2, t);
    float primary = pow(max(1 - d1 * d1, 0), specular.w * hair.z);
    float secondary = pow(max(1 - d2 * d2, 0), specular.w * hair.w);

    float3 diffuse = 0, spec = 0;
    float glow = 0;
    [unroll] for (uint i = 0; i < 3; ++i)
    {
        float3 l = light_dir[i].xyz, c = light_color[i].rgb;
        float nol = dot(n, l), snol = saturate(nol);
        if (nol > 0)
            diffuse += snol / PI * c;
        diffuse += (saturate(nol * velvety_rim.x + velvety_rim.y) - snol) * c * velvety.rgb;
        diffuse += saturate(dot(l, v)) * saturate((1 - nol) * 0.5) * rim_vis * c * rim.rgb;
        float band = max(nol, params[3].z) * saturate((nol + 0.3) * 3.333);
        spec += c * (primary * band) * params[1].rgb + c * (secondary * band) * params[2].rgb;
        glow += (band * primary + band * secondary) * hdr_rate.x;
    }
    spec *= specular.rgb;

    float3 diff_total = hemisphere(n) + 2 * diffuse + ibl_diffuse_light(n) * ibl_diffuse.rgb;
    float3 color = albedo * diff_total + s.x * spec;
    float out_alpha = material_param2.x != 0 ? a : hdr_rate.w * a + glow + hdr_rate.y;
    return finish(color, out_alpha);
}
