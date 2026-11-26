# -*- coding: utf-8 -*-
"""Export TMC + TMCL models from the game to skinned glTF (.glb) with DDS textures.

  python tools\\export_gltf.py --name KAS_MIS_za_16_a
  python tools\\export_gltf.py --all [--workers 8] [--no-textures] [--dds]

Each model becomes out\\models\\<group>\\<name>.glb with its textures decoded to
PNG in out\\models\\<group>\\<name>_tex\\ (--dds also keeps the BC7 originals).
With --all, out\\models\\pairing.csv records which TMCL was used for each TMC.
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
from tmc import Tmc, TmclView

ROOT = r"E:\Games\DMM\DOAX-VenusVacation\DX11_data"
INDEX = r"D:\Projects\YangHui\DOAXVV\index.csv"
OUT = r"D:\Projects\YangHui\DOAXVV\out\models"

FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
SLOT_NAMES = {0: "color"}


def read_inflated(row):
    with open(os.path.join(ROOT, row["folder"], row["hash"]), "rb") as handle:
        return inflate_all(handle.read(), row["key"])


def variant_stem(name):
    """KAS_MIS_za_16_a and KAS_MIS_za_16_c share the stem KAS_MIS_za_16."""
    return re.sub(r"_[a-z]$", "", name)


def group_of(name):
    parts = name.split("_")
    if len(parts) > 1 and len(parts[1]) == 3 and parts[1].isalpha() and parts[1].isupper():
        return parts[1]
    if len(parts[0]) == 3 and parts[0].isalpha() and parts[0].isupper():
        return parts[0]
    return "misc"


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
    weights = [attrs[k].astype(np.float32) for k in sorted(k for k in attrs if k[0] == "weight")]
    count = min(len(joints), len(weights))
    joints, weights = joints[:count], weights[:count]
    if not count:
        return [], []
    total = np.concatenate(weights, axis=1).sum(1, keepdims=True)
    total[total == 0] = 1
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


def export_model(tmc, view, glb_path, textures=True, keep_dds=False):
    gltf = GltfBuilder()
    doc = gltf.doc
    for node in tmc.nodes:
        entry = {"name": node.name or "node%d" % node.index,
                 "matrix": [float(v) for v in node.local.reshape(-1)]}
        if node.children:
            entry["children"] = node.children
        doc["nodes"].append(entry)
    roots = [node.index for node in tmc.nodes if node.parent < 0]
    doc["scenes"][0]["nodes"].extend(roots)

    tex_dir = os.path.splitext(glb_path)[0] + "_tex"
    texture_ids = {}
    cutout = {}

    def texture_id(index):
        if index in texture_ids:
            return texture_ids[index]
        if not textures or index >= view.texture_count():
            return None
        os.makedirs(tex_dir, exist_ok=True)
        data = view.texture(index)
        if keep_dds:
            with open(os.path.join(tex_dir, "%02d.dds" % index), "wb") as handle:
                handle.write(data)
        try:
            rgba, _fmt = decode_dds(data)
        except (ValueError, struct.error):
            texture_ids[index] = None
            return None
        filename = "%02d.png" % index
        write_png(os.path.join(tex_dir, filename), rgba, level=3)
        alpha = rgba[..., 3]
        cutout[index] = ((alpha < 16).mean() > 0.05, (alpha >= 240).mean() > 0.05)
        doc["images"].append({"uri": os.path.basename(tex_dir) + "/" + filename, "mimeType": "image/png"})
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


CANDIDATES = {}


def init_worker(candidates):
    CANDIDATES.update(candidates)


def export_row(task):
    row, rank, textures, keep_dds, out_name = task
    candidates = CANDIDATES
    try:
        tmc = Tmc(read_inflated(row))
    except (KeyError, ValueError, struct.error) as exc:
        return (row["name"], row["folder"], row["hash"], "", "", 0, "tmc error: %s" % exc)
    view, tmcl_row, matches = pair_tmcl(tmc, candidates.get(tmc.tmcl_size, []), rank)
    if view is None:
        return (tmc.name, row["folder"], row["hash"], "", "", 0, "no tmcl (%d by size)" % len(candidates.get(tmc.tmcl_size, [])))
    path = os.path.join(OUT, group_of(tmc.name), out_name + ".glb")
    try:
        stats = export_model(tmc, view, path, textures, keep_dds)
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
    parser.add_argument("--dds", action="store_true", help="also keep the original BC7 DDS next to each PNG")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    tmcs, tmcl = load_index()
    if args.all:
        chosen = tmcs
    else:
        wanted = set(args.name)
        chosen = [row for row in tmcs
                  if row["name"] in wanted or any(len(w) >= 8 and row["hash"].startswith(w) for w in wanted)]
        if not chosen:
            parser.error("no TMC named %s in index.csv" % ", ".join(sorted(wanted)) if wanted else "give --name or --all")
    variants = collections.defaultdict(list)
    for row in sorted(tmcs, key=lambda r: (r["name"], r["hash"])):
        variants[(row["plain_size"], variant_stem(row["name"]))].append(row["hash"])
    used = collections.Counter()
    tasks = []
    for row in sorted(chosen, key=lambda r: (r["name"], r["folder"], r["hash"])):
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", row["name"]) or row["hash"][:16]
        used[base] += 1
        out_name = base if used[base] == 1 else "%s__%s" % (base, row["hash"][:8])
        rank = variants[(row["plain_size"], variant_stem(row["name"]))].index(row["hash"])
        tasks.append((row, rank, not args.no_textures, args.dds, out_name))
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
    log = ""
    if args.all:
        os.makedirs(OUT, exist_ok=True)
        log = os.path.join(OUT, "pairing.csv")
        with open(log, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("name", "tmc_folder", "tmc_hash", "tmcl_folder", "tmcl_hash", "tmcl_matches", "result"))
            writer.writerows(sorted(results))
    status = collections.Counter(result[6].split(" ")[0] if result[6].startswith("ok") else result[6].split(" (")[0].split(":")[0]
                                 for result in results)
    ambiguous = sum(1 for result in results if result[5] > 1)
    print("models", len(results), dict(status), "ambiguous tmcl", ambiguous, "log", log or "-")
    for result in results[:10]:
        print(" ", result[0], result[6], "tmcl", result[4][:16], "matches", result[5])


if __name__ == "__main__":
    main()
