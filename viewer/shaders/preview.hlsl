// Texture preview for the material panel: one channel or rgb over a checkerboard for alpha.

cbuffer Preview : register(b0)
{
    int channel;  // 0 rgb, 1 r, 2 g, 3 b, 4 a, 5 rgba over checker
    int3 pad;
};

Texture2D tex : register(t0);
SamplerState linear_sampler : register(s0);

struct PSIn
{
    float4 clip : SV_Position;
    float2 uv : TEXCOORD0;
};

PSIn vs_main(uint id : SV_VertexID)
{
    PSIn o;
    o.uv = float2((id << 1) & 2, id & 2);
    o.clip = float4(o.uv * float2(2, -2) + float2(-1, 1), 0, 1);
    return o;
}

float4 ps_main(PSIn p) : SV_Target
{
    float4 c = tex.Sample(linear_sampler, p.uv);
    if (channel == 1) return float4(c.rrr, 1);
    if (channel == 2) return float4(c.ggg, 1);
    if (channel == 3) return float4(c.bbb, 1);
    if (channel == 4) return float4(c.aaa, 1);
    if (channel == 5)
    {
        float checker = ((uint(p.clip.x) / 16 + uint(p.clip.y) / 16) & 1) ? 0.6 : 0.4;
        return float4(lerp(checker.xxx, c.rgb, c.a), 1);
    }
    return float4(c.rgb, 1);
}
