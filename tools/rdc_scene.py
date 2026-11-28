# -*- coding: utf-8 -*-
"""Extract the scene of a RenderDoc dump for the viewer's game render mode.

  python tools\\rdc_scene.py out\\renderdoc\\misaki

Needs the dump (tools\\rdc_dump.py: draws\\, buffers\\, textures\\) and the draw matching
(tools\\rdc_match.py: draws_matched.csv). Reads the PBSMat game file (read only) for the
material type names.

The game lights in view space (left handed); everything here is converted to the character
space of our glb files: game world (right handed, like glTF) rotated by the inverse yaw of the
character, so the viewer can light the model at the origin the way the frame lit Misaki.

Writes <dump>\\scene\\:
  scene.json        lights, hemisphere, IBL, tone mapping, bloom, SSS kernel, camera, and per
                    glb material the captured passes (shader family, render state, constants)
  materials.bin     runtime gMaterialParameterList (4096 x 144 bytes, ids from gIDandFresnel.xy;
                    260..321 are the PBSMat types of characters)
  skin_materials.bin  runtime gSkinMaterialParameterList (112 bytes per row)
  ibl_diffuse.dds   ibl_specular.dds   environment cubes (RGBA16F, every mip)
  suntan.png        tan line mask sampled by the skin G-buffer shader (t10)
"""
import argparse
import csv
import json
import math
import os
import re
import shutil
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import export_gltf  # noqa: E402

LIGHTING_CS = "cs_b848e33994e7"
TONEMAP_PS = "ps_4f9e3239f4bf"
SSS_PS = "ps_ab7c1e63266a"
BLOOM_PS = "ps_54500588f263"
BLUR_PS = "ps_fbd21ffdc07a"
PBSMAT_HASH = "f0490863"  # HIGH, 62 entries
PBS_FIRST_ID = 260  # character material id = 256 + 4 + PBSMat index

# pixel shader -> viewer family; forward flags: normal map (t1), spec map (t2), spec from albedo
# (gSpecularVisibilityParam), reflection map (t1 at uv1), diffuse only
FAMILIES = {
    "ps_55b76df67077": ("cloth", []),
    "ps_d0fb033099aa": ("cloth_flat", []),
    "ps_524852116c9f": ("wet_cloth", []),
    "ps_c89ae5936261": ("skin", []),
    "ps_b4bf46237b69": ("hair", []),
    "ps_073e8cdcb837": ("pbs", ["normal_map", "spec_map"]),
    "ps_f9b733188392": ("pbs", ["spec_albedo", "reflection_map"]),
    "ps_6156f8a9b5a8": ("pbs", ["spec_albedo"]),
    "ps_b38733902ee1": ("pbs", ["diffuse_only"]),
    "ps_e368b1eb94af": ("pbs", ["normal_map", "diffuse_only"]),
}

MATERIAL_ROW = [  # gMaterialParameterList, 144 bytes
    ("base_color", 0, 4), ("specular", 16, 4), ("ibl_diffuse", 32, 4), ("ibl_specular", 48, 4),
    ("rim", 64, 4), ("velvety", 80, 4), ("velvety_rim_param", 96, 4), ("ambient", 112, 4),
    ("emissive", 128, 1), ("light_scatter_out_scatter_rate", 132, 1), ("light_scatter_depth_offset", 136, 1),
]
SKIN_ROW = [  # gSkinMaterialParameterList, 112 bytes
    ("material_parameter", 0, 4), ("translucency_light_param", 16, 4), ("sweat_drop_specular", 32, 4),
    ("sweat_drop_ibl_specular", 48, 4), ("wet_light_color", 64, 4), ("wet_light_dir", 80, 4),
    ("flush_param", 96, 4),
]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_draw(dump, event):
    with open(os.path.join(dump, "draws", "%d.json" % event), encoding="utf-8") as fh:
        return json.load(fh)


def find_draw(dump, shader, predicate=None):
    """first draw / dispatch of a shader (events in order)"""
    events = sorted(int(n[:-5]) for n in os.listdir(os.path.join(dump, "draws")) if n.endswith(".json"))
    for event in events:
        d = load_draw(dump, event)
        for stage in d["stages"].values():
            if stage.get("shader") == shader and (predicate is None or predicate(d)):
                return d
    raise SystemExit("no draw uses %s" % shader)


def cbuffer(stage, name):
    for cb in stage["cbuffers"]:
        if cb["name"] == name:
            return cb["values"]
    return {}


def flatten(values):
    """{'gKernel': {'gKernel[0]': [...], ...}} -> {'gKernel': [[...], ...]}"""
    out = {}
    for key, value in values.items():
        if isinstance(value, dict):
            out[key] = [value[k] for k in sorted(value, key=lambda k: int(re.search(r"\[(\d+)\]", k).group(1)))]
        else:
            out[key] = value
    return out


def array(values, key):
    v = values[key]
    return [v[k] for k in sorted(v, key=lambda k: int(re.search(r"\[(\d+)\]", k).group(1)))]


def decode_row(data, layout_):
    out = {}
    for name, offset, count in layout_:
        vals = list(struct.unpack_from("<%df" % count, data, offset))
        out[name] = [round(v, 6) for v in vals] if count > 1 else round(vals[0], 6)
    if len(data) >= 144 and layout_ is MATERIAL_ROW:
        out["flags"] = struct.unpack_from("<I", data, 140)[0]
    return out


def pbs_names():
    rows = read_csv(export_gltf.INDEX)
    row = next(r for r in rows if r["magic"] == "PBSMat" and r["hash"].startswith(PBSMAT_HASH))
    data = export_gltf.read_inflated(row)
    names = {}
    for m in re.finditer(rb"([A-Za-z0-9_]+)\x00PBSMaterialParameters\x00", data):
        names[struct.unpack_from("<I", data, m.start() - 16)[0]] = m.group(1).decode()
    return [names[i] for i in range(len(names))]


def yaw_of(matrices):
    """median yaw of the skinning matrices (3 rows of float4, column-vector convention) that are
    close to a pure Y rotation; limbs posed away from the bind pose are left out"""
    upright = [m for m in matrices if m[5] > 0.97] or matrices
    return float(np.median([math.atan2(m[2], m[0]) for m in upright]))


def rot_y(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def unit(v):
    v = np.asarray(v[:3], dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def r6(v):
    return [round(float(x), 6) for x in v]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", nargs="?", default=os.path.join(export_gltf.OUT, "renderdoc", "misaki"))
    args = ap.parse_args()
    dump = args.dump
    out_dir = os.path.join(dump, "scene")
    os.makedirs(out_dir, exist_ok=True)

    lighting = find_draw(dump, LIGHTING_CS)
    cs = lighting["stages"]["cs"]
    g = cbuffer(cs, "gGlobalParam")
    inv_view = np.array(g["gInvView"], dtype=float).reshape(4, 4)  # row vectors: world = v * M
    view_rot = inv_view[:3, :3]

    def view_to_world(v):
        return unit(np.asarray(v[:3], dtype=float) @ view_rot)

    # character yaw from the body's skinning palette
    matched = read_csv(os.path.join(dump, "draws_matched.csv"))
    skin_body = next(r for r in matched if r["confirmed"] == "True" and r["ps"] == "ps_c89ae5936261"
                     and "/costume/" in r["glb"])
    body = load_draw(dump, int(skin_body["event"]))
    palette = array(cbuffer(body["stages"]["vs"], "skinning_matrix_block"), "gSkinningMatrices")
    mats = [p for p in palette if len(p) == 12]
    yaw = yaw_of(mats)
    rot = rot_y(yaw)  # character space -> game world
    origin = np.array([mats[0][3], mats[0][7], mats[0][11]])

    def world_to_char(v):
        return unit(rot.T @ np.asarray(v[:3], dtype=float))

    dirs = array(g, "gDirectionalLightDir")
    colors = array(g, "gDirectionalLightColor")
    lights = [{"dir": r6(world_to_char(view_to_world(d))), "color": r6(c)} for d, c in zip(dirs, colors)]
    hemi_dir, sky, ground = array(g, "gHemisphereDir"), array(g, "gHemisphereSkyColor"), array(g, "gHemisphereGroundColor")
    hemispheres = [{"dir": r6(world_to_char(view_to_world(hemi_dir[i]))), "sky": r6(sky[i][:3]), "ground": r6(ground[i][:3])}
                   for i in range(len(hemi_dir))]

    # camera of the frame, in character space
    eye = inv_view[3, :3]
    forward = unit(inv_view[2, :3])  # the game view looks along +z
    inv_proj = np.array(g["gInvProjection"], dtype=float).reshape(4, 4)
    fov_y = 2 * math.atan(inv_proj[1, 1])
    camera = {"eye": r6(rot.T @ (eye - origin)), "forward": r6(rot.T @ forward), "fov_y": round(fov_y, 6),
              "aspect": round(inv_proj[0, 0] / inv_proj[1, 1], 6)}

    # IBL cubes and the material tables the dispatch read
    tex = {t["name"]: t for t in cs["textures"]}
    for name, file_name in (("gIblAmbientDiffuseTexture", "ibl_diffuse.dds"), ("gIblAmbientSpecularTexture", "ibl_specular.dds")):
        src = os.path.join(dump, "textures", "%d.dds" % tex[name]["resource"])
        shutil.copyfile(src, os.path.join(out_dir, file_name))
    buffers = {}
    for n in os.listdir(os.path.join(dump, "buffers")):
        if n.endswith(".json"):
            with open(os.path.join(dump, "buffers", n), encoding="utf-8") as fh:
                info = json.load(fh)
            buffers.setdefault(info["name"], info)
    with open(os.path.join(dump, "buffers", "%d.bin" % buffers["gMaterialParameterList"]["resource"]), "rb") as fh:
        material_table = fh.read()
    with open(os.path.join(dump, "buffers", "%d.bin" % buffers["gSkinMaterialParameterList"]["resource"]), "rb") as fh:
        skin_table = fh.read()
    with open(os.path.join(out_dir, "materials.bin"), "wb") as fh:
        fh.write(material_table)
    with open(os.path.join(out_dir, "skin_materials.bin"), "wb") as fh:
        fh.write(skin_table)

    names = pbs_names()
    pbs = [{"name": name, "id": PBS_FIRST_ID + i,
            "row": decode_row(material_table[(PBS_FIRST_ID + i) * 144:(PBS_FIRST_ID + i + 1) * 144], MATERIAL_ROW)}
           for i, name in enumerate(names)]

    # tone mapping, bloom, SSS
    tonemap = find_draw(dump, TONEMAP_PS)
    tv = cbuffer(tonemap["stages"]["ps"], "vector_register_block")
    with open(os.path.join(dump, "buffers", "%d.bin" % buffers["toneCurveTable"]["resource"]), "rb") as fh:
        curve = np.frombuffer(fh.read(), dtype=np.float32).reshape(-1, 4)
    bright = cbuffer(find_draw(dump, BLOOM_PS)["stages"]["ps"], "vector_register_block")
    blur_draw = find_draw(dump, BLUR_PS)
    blur = cbuffer(blur_draw["stages"]["ps"], "vector_register_block")
    # tap pair i sits at +-(2i+1) * step source texels (vertical pass first, it halves the height)
    blur_src_height = int(blur_draw["stages"]["ps"]["textures"][0]["desc"].split()[1].split("x")[1])
    blur_step = array(cbuffer(blur_draw["stages"]["vs"], "vector_register_block"), "Offset")[0][1] * blur_src_height
    sss = cbuffer(find_draw(dump, SSS_PS)["stages"]["ps"], "vector_register_block")
    suntan = None
    sk = body["stages"]["ps"]["textures"]
    for t in sk:
        if t["slot"] == 10:
            src = os.path.join(dump, "textures", "%d.png" % t["resource"])
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(out_dir, "suntan.png"))
                suntan = "suntan.png"

    # captured passes per glb material
    full_size = tex["gGBuffer0Texture"]["desc"].split()[1]
    materials = {}
    seen = set()
    for r in matched:
        if r["confirmed"] != "True" or r["ps"] not in FAMILIES:
            continue
        key = (r["glb"], r["material"], r["pass"])
        if key in seen:
            continue
        seen.add(key)
        d = load_draw(dump, int(r["event"]))
        if not d["targets"] or full_size not in d["targets"][0]:
            continue  # the half resolution copy of the transparent pass
        ps = d["stages"]["ps"]
        family, flags = FAMILIES[r["ps"]]
        default_cb = flatten(cbuffer(ps, "ps_default_cb"))
        params = flatten(cbuffer(ps, "vector_register_block"))
        light_cb = flatten(cbuffer(ps, "ps_light_cb"))
        idf = default_cb.get("gIDandFresnel", [0, 0, 0, 0])
        material_id = int(round(idf[0] * 255)) | (int(round(idf[1] * 255)) << 8)
        entry = materials.setdefault(r["glb"], {}).get(r["material"])
        if entry is None:
            entry = materials[r["glb"]][r["material"]] = {
                "family": family, "flags": flags, "ps": r["ps"], "material_id": material_id, "passes": []}
        else:
            material_id = entry["material_id"]
        # forward shaders take their constants from the cbuffer; only deferred ones read the table
        if family in ("cloth", "cloth_flat", "wet_cloth", "skin") and 0 <= material_id < len(material_table) // 144:
            entry["row"] = decode_row(material_table[material_id * 144:(material_id + 1) * 144], MATERIAL_ROW)
            if PBS_FIRST_ID <= material_id < PBS_FIRST_ID + len(names):
                entry["pbs_name"] = names[material_id - PBS_FIRST_ID]
        if family == "skin":
            skin_index = (int(round(idf[3] * 255)) & 7) - 1
            entry["skin_index"] = skin_index
            entry["skin_row"] = decode_row(skin_table[skin_index * 112:(skin_index + 1) * 112], SKIN_ROW)
        state = d["state"]
        entry["passes"].append({
            "event": int(r["event"]), "pass": int(r["pass"]), "ps": r["ps"],
            "blend": state["blend"][0]["enabled"], "write_mask": state["blend"][0]["write"],
            "depth_write": state["depth"]["write"], "cull": state["raster"]["cull"],
            "stencil_ref": state["depth"]["stencil_ref"],
            "textures": {"t%d" % t["slot"]: t["view_format"] for t in ps["textures"] if t["slot"] < 4},
            "cb": {k: v for k, v in default_cb.items() if k not in ("gEyePosition", "gEyePlane", "gShadowCsBias")},
            "params": params,
            "ambient": light_cb.get("gAmbientColor"),
        })

    scene = {
        "source": os.path.relpath(dump, export_gltf.OUT),
        "character": {"yaw": round(yaw, 6), "origin": r6(origin),
                      "note": "game world = rot_y(yaw) * character + origin (origin: first skinning matrix)"},
        "camera": camera,
        "lights": lights,
        "hemispheres": hemispheres,
        "light_sets": {"character": [0, 1, 2], "environment": [3, 4, 5]},
        "ibl": {"diffuse": "ibl_diffuse.dds", "specular": "ibl_specular.dds", "specular_mips": 7},
        "tonemap": {"exposure": tv["gExposure"][0], "bloom_scale": r6(tv["gBloomScale"]),
                    "curve": r6(curve[:, 0])},
        "bloom": {"offset": r6(bright["gOffset"]), "scale": r6(bright["gScale"]),
                  "weights": [round(w[0], 6) for w in array(blur, "Weight")], "step": round(blur_step, 6)},
        "sss": {"blur_param": [r6(v) for v in array(sss, "gBlurParam")],
                "kernel": [r6(v) for v in array(sss, "gKernel")], "rate": r6(sss["gRateParam"])},
        "suntan": suntan,
        "pbs": pbs,
        "materials": materials,
    }
    with open(os.path.join(out_dir, "scene.json"), "w", encoding="utf-8") as fh:
        json.dump(scene, fh, ensure_ascii=False, indent=1)
    count = sum(len(m) for m in materials.values())
    print("wrote %s: %d lights, %d pbs types, %d materials in %d glb, yaw %.1f deg" % (
        os.path.relpath(out_dir, export_gltf.OUT), len(lights), len(pbs), count, len(materials), math.degrees(yaw)))


if __name__ == "__main__":
    main()
