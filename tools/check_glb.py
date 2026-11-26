# -*- coding: utf-8 -*-
"""Sanity-check exported .glb files: index ranges, joint ranges, weight sums."""
import json
import struct
import sys

import numpy as np

COMPONENTS = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load(path):
    data = open(path, "rb").read()
    magic, _version, _total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError("not a glb")
    json_len = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return doc, data[bin_start:]


def accessor(doc, binary, index):
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    width = WIDTH[acc["type"]]
    array = np.frombuffer(binary, COMPONENTS[acc["componentType"]], acc["count"] * width,
                          view.get("byteOffset", 0) + acc.get("byteOffset", 0))
    return array.reshape(acc["count"], width)


def check(path):
    doc, binary = load(path)
    problems = []
    nodes = {}
    for node in doc["nodes"]:
        if "mesh" in node:
            nodes[node["mesh"]] = node
    triangles = 0
    for mesh_index, mesh in enumerate(doc["meshes"]):
        skin = doc["skins"][nodes[mesh_index]["skin"]] if "skin" in nodes.get(mesh_index, {}) else None
        for prim in mesh["primitives"]:
            attrs = prim["attributes"]
            count = doc["accessors"][attrs["POSITION"]]["count"]
            indices = accessor(doc, binary, prim["indices"]).reshape(-1)
            triangles += len(indices) // 3
            if indices.max() >= count:
                problems.append("%s: index %d >= %d" % (mesh["name"], indices.max(), count))
            positions = accessor(doc, binary, attrs["POSITION"])
            if not np.isfinite(positions).all():
                problems.append("%s: non-finite positions" % mesh["name"])
            if skin is not None:
                weights = sum(accessor(doc, binary, attrs[k]).sum(1) for k in attrs if k.startswith("WEIGHTS_"))
                if np.abs(weights - 1).max() > 1e-3:
                    problems.append("%s: weight sum off by %.4f" % (mesh["name"], np.abs(weights - 1).max()))
                for key in (k for k in attrs if k.startswith("JOINTS_")):
                    joints = accessor(doc, binary, attrs[key])
                    if joints.max() >= len(skin["joints"]):
                        problems.append("%s: %s %d >= %d joints" % (mesh["name"], key, joints.max(), len(skin["joints"])))
    print(path, "meshes", len(doc["meshes"]), "triangles", triangles, "nodes", len(doc["nodes"]),
          "skins", len(doc.get("skins", [])), "textures", len(doc.get("textures", [])),
          "OK" if not problems else "PROBLEMS")
    for problem in problems:
        print("  ", problem)
    return not problems


if __name__ == "__main__":
    results = [check(path) for path in sys.argv[1:]]
    raise SystemExit(0 if all(results) else 1)
