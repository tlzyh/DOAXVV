# -*- coding: utf-8 -*-
"""Export TMC + TMCL models from the game to skinned glTF (.glb) with DDS textures.

  python tools\\export_gltf.py --name KAS_MIS_za_16_a
  python tools\\export_gltf.py --all [--workers 8] [--no-textures] [--dds]
  python tools\\export_gltf.py --all --retry-failed   (only TMCs not yet ok in pairing.csv or whose glb is
                                                     not at its current path, e.g. new or renamed files)
  python tools\\export_gltf.py --name KAS_MIS_za_16_a --motion fe23605cfac8 --clip 1 [--fps 60]
  python tools\\export_gltf.py --name KAS_MIS_za_16_a --name 3dfbeda0 --motion fe23605cfac8:1 --motion 0f64ff100d53:5

Each model becomes out\\models\\<category>\\<group>\\<name>.glb with its textures
decoded to <name>_tex\\NN.png next to it, NN being the texture's order in the TMCL
(see layout.py; --dds also keeps the BC7 originals as NN.dds). With --all,
out\\catalog\\pairing.csv records which TMCL was used for each TMC.
"""
import argparse
import collections
import csv
import json
import multiprocessing
import os
import re
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from bcdec import decode_dds, write_png
from decrypt import inflate_all
from motion import euler_to_quat, hemisphere, motions, quat_mul, quat_rotate
from tmc import Tmc, TmclView
import layout

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = layout.INDEX
OUT = layout.OUT

FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
SLOT_NAMES = {0: "color"}


def read_inflated(row):
    with open(os.path.join(ROOT, row["folder"], row["hash"]), "rb") as handle:
        return inflate_all(handle.read(), row["key"])


def variant_stem(name):
    """KAS_MIS_za_16_a and KAS_MIS_za_16_c share the stem KAS_MIS_za_16."""
    return re.sub(r"_[a-z]$", "", name)


class GltfBuilder:
    def __init__(self):
        self.bin = bytearray()
        self.doc = {
            "asset": {"version": "2.0", "generator": "DOAXVV tools/export_gltf.py"},
            "scene": 0, "scenes": [{"nodes": []}],
            "nodes": [], "meshes": [], "skins": [], "materials": [],
            "textures": [], "images": [], "samplers": [{"magFilter": 9729, "minFilter": 9987}],
            "accessors": [], "bufferViews": [], "buffers": [],
        }

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin.extend(data)
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, array, kind, component, target=ARRAY_BUFFER, bounds=False, normalized=False):
        array = np.ascontiguousarray(array)
        acc = {"bufferView": self.view(array.tobytes(), target), "componentType": component,
               "count": int(array.shape[0]), "type": kind}
        if normalized:
            acc["normalized"] = True
        if bounds:
            acc["min"] = [float(v) for v in array.min(0)]
            acc["max"] = [float(v) for v in array.max(0)]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def finish(self, path):
        doc = {key: value for key, value in self.doc.items() if value != []}
        if not self.doc["textures"]:
            doc.pop("samplers", None)
        doc["buffers"] = [{"byteLength": len(self.bin)}]
        text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        text += b" " * (-len(text) % 4)
        binary = bytes(self.bin) + b"\x00" * (-len(self.bin) % 4)
        total = 12 + 8 + len(text) + 8 + len(binary)
        with open(path, "wb") as handle:
            handle.write(struct.pack("<III", 0x46546C67, 2, total))
            handle.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
            handle.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


def uv_sets(attrs):
    sets = []
    for key in sorted(k for k in attrs if k[0] == "uv"):
        column = attrs[key].astype(np.float32)
        for start in range(0, column.shape[1], 2):
            sets.append(column[:, start:start + 2])
    return sets


def skin_sets(attrs):
    joints = [attrs[k] for k in sorted(k for k in attrs if k[0] == "joint")]
    weights = [np.nan_to_num(attrs[k].astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
               for k in sorted(k for k in attrs if k[0] == "weight")]
    count = min(len(joints), len(weights))
    joints, weights = joints[:count], weights[:count]
    if not count:
        return [], []
    total = np.concatenate(weights, axis=1).sum(1, keepdims=True)
    unweighted = total[:, 0] == 0
    weights[0][unweighted, 0] = 1
    total[unweighted] = 1
    weights = [w / total for w in weights]
    joints = [np.where(w > 0, j, 0).astype(np.uint8) for j, w in zip(joints, weights)]
    return joints, weights


def strip_to_list(strip):
    tris = np.stack([strip[:-2], strip[1:-1], strip[2:]], axis=1)
    tris[1::2, [1, 2]] = tris[1::2, [2, 1]]
    keep = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    return tris[keep].reshape(-1)


def unit(vectors):
    length = np.linalg.norm(vectors, axis=1, keepdims=True)
    length[length == 0] = 1
    return vectors / length


def matrix_to_quat(m):
    """Column-vector rotation matrix -> xyzw quaternion."""
    w = np.sqrt(max(0.0, 1 + m[0, 0] + m[1, 1] + m[2, 2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + m[0, 0] - m[1, 1] - m[2, 2])) / 2, m[2, 1] - m[1, 2])
    y = np.copysign(np.sqrt(max(0.0, 1 - m[0, 0] + m[1, 1] - m[2, 2])) / 2, m[0, 2] - m[2, 0])
    z = np.copysign(np.sqrt(max(0.0, 1 - m[0, 0] - m[1, 1] + m[2, 2])) / 2, m[1, 0] - m[0, 1])
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q)


def bind_trs(local):
    """Row-vector local matrix (S * R * T) -> glTF translation, rotation, scale."""
    scale = np.linalg.norm(local[:3, :3], axis=1)
    rotation = matrix_to_quat((local[:3, :3] / np.where(scale == 0, 1, scale)[:, None]).T)
    return local[3, :3].copy(), rotation, scale


def motion_targets(tmc, motion):
    """{motion node: TMC node}, or {} if the model lacks the motion's bones.

    A motion drives the subtree under the TMC node named like its root, sorted
    by lower-cased bone name (MOT00_Hips .. MOT20_RightToe, OPT_Face_c_eyebrow ..
    OPT_Face_r_nose_d, OPT_Face_Root). When
    that subtree holds more bones (the body under MOT00_Hips), only names with
    the root's leading letters (MOT) count.
    """
    root = next((node for node in tmc.nodes if node.name == motion.name), None)
    if root is None:
        return {}
    group, stack = [], [root.index]
    while stack:
        index = stack.pop()
        group.append(index)
        stack.extend(tmc.nodes[index].children)
    if len(group) != motion.node_count:
        prefix = re.match(r"[A-Za-z]*", motion.name).group(0)
        group = [i for i in group if tmc.nodes[i].name.startswith(prefix)]
    group.sort(key=lambda i: tmc.nodes[i].name.lower())
    if len(group) != motion.node_count:
        return {}
    position = {index: number for number, index in enumerate(group)}
    parents = [position.get(tmc.nodes[index].parent, -1) for index in group]
    return dict(enumerate(group)) if parents == list(motion.parents) else {}


def leg_ratio(tmc, targets, channels):
    """Model leg length / motion leg length, used to rescale the root translation."""
    chain = [i for i in targets if tmc.nodes[targets[i]].name.split("_", 1)[-1] in ("LeftUpLeg", "LeftLeg", "LeftFoot")]
    model = sum(np.linalg.norm(tmc.nodes[targets[i]].local[3, :3]) for i in chain)
    source = sum(np.linalg.norm(channels[0, i, :3]) for i in chain)
    return model / source if chain and source > 0 else 1.0


def build_rig(body, motion, channels):
    """World transforms of the motion's bones on a body skeleton, per frame.

    Separate models (hair rooted at MOT01_Head, faces at MOT15_Neck) take these
    for their root so they follow the body. Bone scale is ignored here.
    """
    targets = motion_targets(body, motion)
    if len(targets) != motion.node_count:
        return None
    ratio = leg_ratio(body, targets, channels)
    local_q = euler_to_quat(channels[:, :, 3:6])
    frames, count = channels.shape[:2]
    world_q, world_t = np.zeros((frames, count, 4)), np.zeros((frames, count, 3))
    done = set()
    while len(done) < count:
        for i in range(count):
            parent = motion.parents[i]
            if i in done or (parent >= 0 and parent not in done):
                continue
            if parent < 0:
                world_q[:, i], world_t[:, i] = local_q[:, i], channels[:, i, 0:3] * ratio
            else:
                bind = np.broadcast_to(body.nodes[targets[i]].local[3, :3], (frames, 3))
                world_q[:, i] = quat_mul(world_q[:, parent], local_q[:, i])
                world_t[:, i] = world_t[:, parent] + quat_rotate(world_q[:, parent], bind)
            done.add(i)
    return {"motion": motion, "names": [body.nodes[targets[i]].name for i in range(count)],
            "rotation": hemisphere(world_q), "translation": world_t}


def add_animations(gltf, tmc, animations):
    doc = gltf.doc
    doc["animations"] = []
    by_name = {node.name: node.index for node in tmc.nodes}
    for name, banks, fps, rig in animations:
        samplers, anim_channels, times = [], [], {}

        def track(node, path, values, kind):
            frames = len(values)
            if frames not in times:
                times[frames] = gltf.accessor((np.arange(frames) / fps).astype(np.float32)[:, None], "SCALAR", FLOAT,
                                              target=None, bounds=True)
            samplers.append({"input": times[frames], "interpolation": "LINEAR",
                             "output": gltf.accessor(values.astype(np.float32), kind, FLOAT, target=None)})
            anim_channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})

        ratio = 1.0
        for motion, channels in banks:
            targets = motion_targets(tmc, motion)
            if targets:
                # Expressions move face bones; the face rig shares the model's proportions.
                expression = motion.name.startswith("OPT_Face")
                for i, node in targets.items():
                    if tmc.nodes[node].parent < 0:
                        ratio = leg_ratio(tmc, targets, channels)
                        track(node, "translation", channels[:, i, 0:3] * ratio, "VEC3")
                    elif expression:
                        track(node, "translation", channels[:, i, 0:3], "VEC3")
                    track(node, "rotation", euler_to_quat(channels[:, i, 3:6]), "VEC4")
                    track(node, "scale", channels[:, i, 6:9], "VEC3")
            elif rig is not None and rig["motion"] is motion:
                for i, bone in enumerate(rig["names"]):
                    node = by_name.get(bone)
                    if node is None:
                        continue
                    if tmc.nodes[node].parent < 0:
                        track(node, "translation", rig["translation"][:, i], "VEC3")
                        track(node, "rotation", rig["rotation"][:, i], "VEC4")
                    else:
                        track(node, "rotation", euler_to_quat(channels[:, i, 3:6]), "VEC4")
        if anim_channels:
            doc["animations"].append({"name": name, "samplers": samplers, "channels": anim_channels,
                                      "extras": {"root_scale": float(ratio), "fps": fps}})


def export_model(tmc, view, glb_path, textures=True, keep_dds=False, animations=None):
    gltf = GltfBuilder()
    doc = gltf.doc
    animated = set()
    for _name, banks, _fps, rig in animations or []:
        for motion, _channels in banks:
            animated.update(motion_targets(tmc, motion).values())
        if rig is not None:
            animated.update(node.index for node in tmc.nodes if node.name in rig["names"])
    for node in tmc.nodes:
        entry = {"name": node.name or "node%d" % node.index}
        if node.index in animated:
            translation, rotation, scale = bind_trs(node.local)
            entry.update(translation=[float(v) for v in translation], rotation=[float(v) for v in rotation],
                         scale=[float(v) for v in scale])
        else:
            entry["matrix"] = [float(v) for v in node.local.reshape(-1)]
        if node.children:
            entry["children"] = node.children
        doc["nodes"].append(entry)
    roots = [node.index for node in tmc.nodes if node.parent < 0]
    doc["scenes"][0]["nodes"].extend(roots)

    texture_ids = {}
    cutout = {}

    def texture_id(index):
        if index in texture_ids:
            return texture_ids[index]
        if not textures or index >= view.texture_count():
            return None
        data = view.texture(index)
        try:
            rgba, _fmt = decode_dds(data)
        except (ValueError, struct.error):
            texture_ids[index] = None
            return None
        tex_dir = layout.tex_dir(glb_path)
        os.makedirs(tex_dir, exist_ok=True)
        filename = "%02d.png" % index
        write_png(os.path.join(tex_dir, filename), rgba, level=3)
        if keep_dds:
            with open(os.path.join(tex_dir, "%02d.dds" % index), "wb") as handle:
                handle.write(data)
        alpha = rgba[..., 3]
        cutout[index] = ((alpha < 16).mean() > 0.05, (alpha >= 240).mean() > 0.05)
        doc["images"].append({"uri": os.path.basename(tex_dir) + "/" + filename, "mimeType": "image/png",
                              "extras": {"tmcl_texture": index}})
        doc["textures"].append({"sampler": 0, "source": len(doc["images"]) - 1})
        texture_ids[index] = len(doc["textures"]) - 1
        return texture_ids[index]

    material_ids = {}

    def material_id(submesh):
        refs = tuple((ref.slot, ref.uv, ref.texture) for ref in submesh.textures)
        key = (submesh.material, refs)
        if key in material_ids:
            return material_ids[key]
        material = {"name": "mtl%d_%d" % (submesh.material, len(material_ids)),
                    "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.8},
                    "doubleSided": True,
                    "extras": {"tmc_material": submesh.material,
                               "textures": [{"slot": s, "uv": u, "texture": t} for s, u, t in refs]}}
        for slot, uv, texture in refs:
            if slot == 0:
                tid = texture_id(texture)
                if tid is not None:
                    material["pbrMetallicRoughness"]["baseColorTexture"] = {"index": tid, "texCoord": uv}
                    # Skin alpha is a shading mask; overlays (lashes, brows) have no normal map in slot 2.
                    has_holes, has_solid = cutout.get(texture, (False, False))
                    if has_holes and has_solid:
                        material["alphaMode"] = "MASK"
                        material["alphaCutoff"] = 0.5
                    elif has_holes and not any(s == 2 for s, _u, _t in refs):
                        material["alphaMode"] = "BLEND"
            else:
                texture_id(texture)
        if submesh.material < len(tmc.materials):
            material["extras"]["mtrcol"] = [[round(float(v), 6) for v in row] for row in tmc.materials[submesh.material]]
        doc["materials"].append(material)
        material_ids[key] = len(doc["materials"]) - 1
        return material_ids[key]

    for obj in tmc.objects:
        mesh_node = tmc.mesh_nodes.get(obj.index)
        decl_attrs = {}
        primitives = []
        for submesh in obj.submeshes:
            decl = obj.decls[submesh.decl]
            if submesh.decl not in decl_attrs:
                raw = view.attributes(decl)
                attrs = {"POSITION": gltf.accessor(raw[("position", 0)][:, :3].astype(np.float32), "VEC3", FLOAT,
                                                   bounds=True)}
                if ("normal", 0) in raw:
                    attrs["NORMAL"] = gltf.accessor(unit(raw[("normal", 0)][:, :3].astype(np.float32)), "VEC3", FLOAT)
                if ("tangent", 0) in raw:
                    tangent = raw[("tangent", 0)].astype(np.float32)
                    tangent[:, :3] = unit(tangent[:, :3])
                    tangent[:, 3] = np.where(tangent[:, 3] < 0, -1.0, 1.0)
                    attrs["TANGENT"] = gltf.accessor(tangent, "VEC4", FLOAT)
                for number, uv in enumerate(uv_sets(raw)):
                    attrs["TEXCOORD_%d" % number] = gltf.accessor(uv, "VEC2", FLOAT)
                if mesh_node is not None:
                    joints, weights = skin_sets(raw)
                    for number, (joint, weight) in enumerate(zip(joints, weights)):
                        attrs["JOINTS_%d" % number] = gltf.accessor(joint, "VEC4", UBYTE)
                        attrs["WEIGHTS_%d" % number] = gltf.accessor(weight, "VEC4", FLOAT)
                decl_attrs[submesh.decl] = attrs
            indices = view.index_array(decl.buffer)[submesh.index_start:submesh.index_start + submesh.index_count]
            if len(indices) % 3:
                indices = strip_to_list(indices)
            if not len(indices):
                continue
            primitives.append({
                "attributes": decl_attrs[submesh.decl],
                "indices": gltf.accessor(indices.astype(np.uint16), "SCALAR", USHORT, ELEMENT_ARRAY_BUFFER),
                "material": material_id(submesh),
                "mode": 4,
            })
        if not primitives:
            continue
        doc["meshes"].append({"name": obj.name, "primitives": primitives})
        node = {"name": "mesh_" + obj.name, "mesh": len(doc["meshes"]) - 1}
        if mesh_node is not None and mesh_node.palette:
            # Vertices are stored in the space of the mesh's owner node (e.g. the head for hair).
            owner = tmc.nodes[mesh_node.node].global_matrix
            inverse = np.stack([(owner @ tmc.nodes[j].inverse_bind).reshape(-1)
                                for j in mesh_node.palette]).astype(np.float32)
            doc["skins"].append({"name": obj.name, "joints": list(mesh_node.palette),
                                 "inverseBindMatrices": gltf.accessor(inverse, "MAT4", FLOAT, target=None),
                                 "skeleton": roots[0]})
            node["skin"] = len(doc["skins"]) - 1
        doc["nodes"].append(node)
        doc["scenes"][0]["nodes"].append(len(doc["nodes"]) - 1)
    if animations:
        add_animations(gltf, tmc, animations)
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)
    gltf.finish(glb_path)
    return {"meshes": len(doc["meshes"]), "textures": len(doc["textures"]), "nodes": len(tmc.nodes)}


def load_index():
    rows = list(csv.DictReader(open(INDEX, encoding="utf-8")))
    tmcl = collections.defaultdict(list)
    for row in rows:
        if row["magic"] == "TMCL" and row["plain_size"]:
            tmcl[int(row["plain_size"])].append(row)
    tmcs = [row for row in rows if row["magic"] == "TMC"]
    pairs = os.path.join(OUT, "tmc_pairs.csv")
    if os.path.exists(pairs):
        by_hash = {row["hash"]: row for row in rows if row["magic"] == "TMCL"}
        tmcl["official"] = {r["tmc"]: by_hash[r["tmcl"]] for r in csv.DictReader(open(pairs, encoding="utf-8"))
                            if r["tmcl"] in by_hash}
    tmcl["types"] = layout.directory_types()
    return tmcs, tmcl


def pair_tmcl(tmc, candidates, rank=0):
    """Return (view, row, number of distinct matching candidates).

    TMC variants that differ only in their name (e.g. _a / _c colorways) match
    the same set of TMCLs; the rank-th variant takes the rank-th match by hash.
    """
    matches = []
    seen = set()
    for row in sorted(candidates, key=lambda r: r["hash"]):
        signature = (row["size"], row["key"])
        if signature in seen:
            continue
        seen.add(signature)
        try:
            view = TmclView(tmc, read_inflated(row))
            if view.check() and view.bounds_match():
                matches.append((view, row))
        except (KeyError, IndexError, ValueError, struct.error):
            continue
    if not matches:
        return None, None, 0
    view, row = matches[rank % len(matches)]
    return view, row, len(matches)


def load_bank_clips(spec, default_clips):
    """'HASH[:1,2|all]' -> [(name, [(motion, channels (frames, nodes, 9))])], one entry per clip.

    Every multi-bone motion bank in the char_dat (body, left + right hand, or
    face) contributes the same clip index.
    """
    prefix, _sep, clip_text = spec.partition(":")
    rows = [row for row in csv.DictReader(open(INDEX, encoding="utf-8"))
            if row["magic"] == "char_dat" and len(prefix) >= 8 and row["hash"].startswith(prefix)]
    if not rows:
        raise SystemExit("no char_dat with hash prefix %s" % prefix)
    banks = [m for m in motions(read_inflated(rows[0])) if m.node_count > 1]
    if not banks:
        raise SystemExit("%s holds no character motion" % prefix)
    if clip_text == "all":
        clips = list(range(len(banks[0].clips)))
    elif clip_text:
        clips = [int(c) for c in clip_text.split(",")]
    else:
        clips = default_clips or [next((c for c in range(len(banks[0].clips)) if banks[0].clip_frames(c) > 1), 0)]
    out = []
    for clip in clips:
        chosen = []
        for bank in banks:
            if clip < len(bank.clips):
                frames = bank.clip_frames(clip) + 1
                chosen.append((bank, bank.channels(np.arange(frames), clip)))
        out.append(("%s_%d" % (rows[0]["hash"][:8], clip), chosen))
    return out


def character_id(char):
    """'mis' or '11' / '0x0b' -> character id (chr_characters.csv)."""
    if re.fullmatch(r"\d+|0x[0-9a-fA-F]+", char):
        return int(char, 0)
    path = os.path.join(OUT, "chr_characters.csv")
    if not os.path.exists(path):
        raise SystemExit("run tools\\chr_data.py first")
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["code"] == char.lower():
            return int(r["char_id"])
    raise SystemExit("no character %s in chr_characters.csv" % char)


def official_partners(prefix, sets, char_id=None):
    """Face / hand / breast banks that the game's mot table plays with body `prefix` (most common set)."""
    found = collections.Counter()
    for row in sets:
        if char_id is not None and int(row["id"], 16) & 0xFFFF != char_id:
            continue
        banks = row["banks"].split()
        kinds = row["kinds"].split()
        if not any(h.startswith(prefix) and k == "body" for h, k in zip(banks, kinds)):
            continue
        found[tuple(h for h, k in zip(banks, kinds) if k in ("face", "hand", "breast"))] += 1
    if not found:
        return None
    if len(found) > 1:
        print("body motion %s appears in %d mot rows with %d partner sets; using the most common "
              "(pick one with --char)" % (prefix, sum(found.values()), len(found)))
    return list(found.most_common(1)[0][0])


def add_partners(specs, char=None):
    """Append the face / hand / breast files the game plays with each body file.

    Uses out\\chr_motion_sets.csv (the game's own mot table, tools\\chr_data.py) when present,
    otherwise the clip-length guess in out\\motion_sets.csv (unique pairs only).
    """
    official = os.path.join(OUT, "chr_motion_sets.csv")
    if os.path.exists(official):
        sets = list(csv.DictReader(open(official, encoding="utf-8")))
        char_id = character_id(char) if char else None
        out = list(specs)
        for spec in specs:
            prefix, sep, clips = spec.partition(":")
            partners = official_partners(prefix, sets, char_id)
            if partners is None:
                if char_id is not None:
                    print("body motion %s is not in character %s's mot table" % (prefix, char))
                continue
            out.extend(h[:16] + sep + clips for h in partners if not any(s.startswith(h[:16]) for s in out))
        return out
    sets = os.path.join(OUT, "motion_sets.csv")
    if not os.path.exists(sets):
        raise SystemExit("run tools\\pair_motion.py first")
    rows = list(csv.DictReader(open(sets, encoding="utf-8")))
    out = list(specs)
    for spec in specs:
        prefix, sep, clips = spec.partition(":")
        row = next((r for r in rows if any(h.startswith(prefix) for h in r["body"].split())), None)
        if row is None:
            continue
        if len(row["body"].split()) != 1:
            print("body motion %s shares its clip lengths with other bodies; no partners added" % prefix)
            continue
        for kind in ("hand", "breast", "hips"):
            if len(row[kind].split()) == 1:
                out.append(row[kind][:16] + sep + clips)
    return out


def load_animations(specs, default_clips, fps):
    """[(name, banks, fps, rig)]; the k-th clip of every --motion plays together as animation k."""
    per_spec = [load_bank_clips(spec, default_clips) for spec in specs]
    out = []
    for k in range(max(len(clips) for clips in per_spec)):
        parts = [clips[k] for clips in per_spec if k < len(clips)]
        out.append(("+".join(name for name, _banks in parts), [b for _name, banks in parts for b in banks], fps, None))
    return out


def attach_rig(animations, rows):
    """Give each animation the world pose of the first chosen body it fully drives."""
    for row in rows:
        body = Tmc(read_inflated(row))
        rigs = [next((build_rig(body, m, c) for m, c in banks if m.node_count == 21), None)
                for _name, banks, _fps, _rig in animations]
        if any(rig is not None for rig in rigs):
            return [(name, banks, fps, rig) for (name, banks, fps, _old), rig in zip(animations, rigs)]
    if any(m.node_count == 21 for _name, banks, _fps, _rig in animations for m, _c in banks):
        print("no body model among --name; hair and face roots will not follow the body motion "
              "(export them together with the body)")
    return animations


CANDIDATES = {}


def init_worker(candidates):
    CANDIDATES.update(candidates)


def export_row(task):
    row, rank, textures, keep_dds, out_name, skip_existing, animations = task
    candidates = CANDIDATES
    try:
        tmc = Tmc(read_inflated(row))
    except (KeyError, ValueError, struct.error) as exc:
        return (row["name"], row["folder"], row["hash"], "", "", 0, "tmc error: %s" % exc)
    official = candidates.get("official", {}).get(row["hash"])
    view = None
    if official is not None:
        view, tmcl_row, _n = pair_tmcl(tmc, [official])
        matches = "official"
    if view is None:
        view, tmcl_row, matches = pair_tmcl(tmc, candidates.get(tmc.tmcl_size, []), rank)
    if view is None:
        return (tmc.name, row["folder"], row["hash"], "", "", 0, "no tmcl (%d by size)" % len(candidates.get(tmc.tmcl_size, [])))
    path = layout.model_path(layout.category_of(row["hash"], candidates.get("types", {})),
                             layout.group_of(row["name"]), out_name)
    if skip_existing and os.path.exists(path):
        return (tmc.name, row["folder"], row["hash"], tmcl_row["folder"], tmcl_row["hash"], matches, "ok skipped")
    try:
        stats = export_model(tmc, view, path, textures, keep_dds, animations)
    except (KeyError, IndexError, ValueError, struct.error) as exc:
        return (tmc.name, row["folder"], row["hash"], tmcl_row["folder"], tmcl_row["hash"], matches, "export error: %s" % exc)
    note = "ok meshes=%(meshes)d textures=%(textures)d" % stats
    return (tmc.name, row["folder"], row["hash"], tmcl_row["folder"], tmcl_row["hash"], matches, note)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", action="append", default=[],
                        help="TMC resource name or hash prefix of at least 8 chars (repeatable)")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-textures", action="store_true")
    parser.add_argument("--skip-existing", action="store_true", help="keep .glb files that are already exported")
    parser.add_argument("--retry-failed", action="store_true",
                        help="with --all: only redo models whose pairing.csv result is not ok or whose glb is "
                             "missing at its current path, keep the rest")
    parser.add_argument("--dds", action="store_true", help="also keep the original BC7 DDS next to each PNG")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--motion", action="append", default=[],
                        help="char_dat hash prefix (>= 8 chars), optionally :CLIP[,CLIP..] or :all (repeatable; "
                             "the k-th clips of all --motion play together)")
    parser.add_argument("--clip", type=int, action="append", default=[],
                        help="clip index in the motion bank (repeatable; default: first clip longer than 1 frame)")
    parser.add_argument("--fps", type=float, default=60.0, help="motion frames per second (default 60)")
    parser.add_argument("--paired", action="store_true",
                        help="also load the face / hand / breast motions the game plays with each body --motion "
                             "(chr_motion_sets.csv, else the clip-length guess in motion_sets.csv)")
    parser.add_argument("--char", help="with --paired: character code (mis, kas, ...) or id whose mot table to use")
    args = parser.parse_args()
    if args.paired:
        args.motion = add_partners(args.motion, args.char)
    animations = load_animations(args.motion, args.clip, args.fps) if args.motion else None
    if animations and args.all:
        parser.error("--motion only works with --name")
    tmcs, tmcl = load_index()
    if args.all:
        chosen = tmcs
    else:
        wanted = set(args.name)
        chosen = [row for row in tmcs
                  if row["name"] in wanted or any(len(w) >= 8 and row["hash"].startswith(w) for w in wanted)]
        if not chosen:
            parser.error("no TMC named %s in index.csv" % ", ".join(sorted(wanted)) if wanted else "give --name or --all")
    if animations:
        animations = attach_rig(animations, chosen)
    variants = collections.defaultdict(list)
    for row in sorted(tmcs, key=lambda r: (r["name"], r["hash"])):
        variants[(row["plain_size"], variant_stem(row["name"]))].append(row["hash"])
    log = os.path.join(layout.CATALOG, "pairing.csv")
    kept = []
    if args.retry_failed:
        previous = [tuple(r.values()) for r in csv.DictReader(open(log, encoding="utf-8"))]
        kept = [r for r in previous if r[6].startswith("ok")]
        done_hashes = {r[2] for r in kept}
    names = layout.out_names(tmcs)
    seen = set()
    tasks = []
    for row in sorted(chosen, key=lambda r: (r["name"], os.path.isabs(r["folder"]), r["folder"], r["hash"])):
        if row["hash"] in seen:
            continue
        seen.add(row["hash"])
        out_name = names[row["hash"]]
        if animations:
            out_name += "_anim"
        if args.retry_failed and row["hash"] in done_hashes and os.path.exists(
                layout.model_path(layout.category_of(row["hash"], tmcl["types"]), layout.group_of(row["name"]),
                                  out_name)):
            continue
        rank = variants[(row["plain_size"], variant_stem(row["name"]))].index(row["hash"])
        tasks.append((row, rank, not args.no_textures, args.dds, out_name, args.skip_existing, animations))
    redo = {task[0]["hash"] for task in tasks}
    kept = [r for r in kept if r[2] in names and r[2] not in redo]
    results = []
    if len(tasks) == 1 or args.workers == 1:
        init_worker(tmcl)
        results = [export_row(task) for task in tasks]
    else:
        with multiprocessing.Pool(args.workers, initializer=init_worker, initargs=(dict(tmcl),)) as pool:
            for done, result in enumerate(pool.imap_unordered(export_row, tasks, chunksize=4), 1):
                results.append(result)
                if done % 100 == 0:
                    print("models", done, "/", len(tasks), flush=True)
    if args.all:
        os.makedirs(layout.CATALOG, exist_ok=True)
        with open(log, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("name", "tmc_folder", "tmc_hash", "tmcl_folder", "tmcl_hash", "tmcl_matches", "result"))
            writer.writerows(sorted(kept + [tuple(str(v) for v in r) for r in results]))
    else:
        log = ""
    status = collections.Counter(result[6].split(" ")[0] if result[6].startswith("ok") else result[6].split(" (")[0].split(":")[0]
                                 for result in results)
    ambiguous = sum(1 for result in results if isinstance(result[5], int) and result[5] > 1)
    print("models", len(results), dict(status), "ambiguous tmcl", ambiguous, "log", log or "-")
    for result in results[:10]:
        print(" ", result[0], result[6], "tmcl", result[4][:16], "matches", result[5])


if __name__ == "__main__":
    main()
