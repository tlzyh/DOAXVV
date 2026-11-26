# -*- coding: utf-8 -*-
"""Parse a KTGL TMC model container and its TMCL data file.

Every block starts with the same header:
  +0x00 char[8] name        +0x0C u32 header size (0x30, or 0x50 for blocks whose data lives in the TMCL)
  +0x10 u32 block size      +0x14 u32 entry count
  +0x20 u32 offset of the entry offset table (relative to the block)
  +0x24 u32 offset of a second table (sizes), +0x28 u32 offset of a nested block
Matrices are row-major with the translation in the last row (row vectors),
which is the same float order glTF expects for column-major column-vector matrices.
"""
import struct

import numpy as np

# GeoDecl element types: (numpy dtype, component count)
ELEMENT_TYPES = {
    0x00: ("<f4", 1), 0x01: ("<f4", 2), 0x02: ("<f4", 3), 0x03: ("<f4", 4),
    0x04: ("u1", 4), 0x05: ("u1", 4), 0x08: ("u1", 4),
    0x0A: ("<f2", 2), 0x0B: ("<f2", 4),
}
USAGE_NAMES = {0: "position", 1: "weight", 2: "joint", 3: "normal", 5: "uv", 6: "tangent", 10: "color"}
SECTION_KINDS = ("TTDL", "VtxLay", "IdxLay")


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def i32(buf, off):
    return struct.unpack_from("<i", buf, off)[0]


def cstr(buf, off, limit=64):
    return buf[off:off + limit].split(b"\x00", 1)[0].decode("ascii", "replace")


class Block:
    def __init__(self, buf, off):
        self.buf = buf
        self.off = off
        self.name = cstr(buf, off, 8)
        self.header = u32(buf, off + 0x0C)
        self.size = u32(buf, off + 0x10)
        self.count = u32(buf, off + 0x14)
        self.table = u32(buf, off + 0x20)
        self.table2 = u32(buf, off + 0x24)
        self.nested = u32(buf, off + 0x28)

    def entries(self):
        if not self.count or not self.table:
            return []
        rel = struct.unpack_from("<%dI" % self.count, self.buf, self.off + self.table)
        return [self.off + value if value else 0 for value in rel]

    def sizes(self):
        return list(struct.unpack_from("<%dI" % self.count, self.buf, self.off + self.table2))

    def child(self, index):
        return Block(self.buf, self.entries()[index])


class Layout:
    """VtxLay / IdxLay / TTDL / LHeader: data stored in TMCL sections."""

    def __init__(self, block):
        self.block = block
        self.total = u32(block.buf, block.off + 0x44)
        self.offsets = list(struct.unpack_from("<%dI" % block.count, block.buf, block.off + block.table))
        self.sizes = list(struct.unpack_from("<%dI" % block.count, block.buf, block.off + block.table2))


class Element:
    def __init__(self, buf, off):
        self.stream, self.offset, self.type = struct.unpack_from("<HHH", buf, off)
        self.usage, self.index = buf[off + 6], buf[off + 7]

    @property
    def usage_name(self):
        return USAGE_NAMES.get(self.usage, "usage%d" % self.usage)


class Decl:
    def __init__(self, buf, off):
        self.buffer = u32(buf, off + 0x0C)
        self.index_count = u32(buf, off + 0x10)
        self.vertex_count = u32(buf, off + 0x14)
        self.topology = u32(buf, off + 0x18)
        self.stride = u32(buf, off + 0x44)
        count = u32(buf, off + 0x48)
        self.elements = [Element(buf, off + 0x58 + 8 * i) for i in range(count)]


class TexRef:
    def __init__(self, buf, off):
        self.slot, self.uv, self.texture = struct.unpack_from("<III", buf, off)


class Submesh:
    def __init__(self, buf, off):
        self.index = u32(buf, off)
        self.material = u32(buf, off + 0x04)
        count = u32(buf, off + 0x10)
        rel = struct.unpack_from("<%dI" % count, buf, off + 0x14)
        self.textures = [TexRef(buf, off + value) for value in rel]
        self.decl = u32(buf, off + 0x3C)
        self.index_start, self.index_count, self.vertex_start, self.vertex_count = struct.unpack_from(
            "<4I", buf, off + 0x80)


class ObjGeo:
    def __init__(self, block):
        buf = block.buf
        self.index = u32(buf, block.off + 0x34)
        self.name = cstr(buf, block.off + 0x60, 16)
        self.submeshes = [Submesh(buf, off) for off in block.entries()]
        decls = Block(buf, block.off + block.nested)
        self.decls = [Decl(buf, off) for off in decls.entries()]


class Bounds:
    def __init__(self, buf, off):
        self.center = np.frombuffer(buf, "<f4", 3, off + 0xF0).copy()
        self.extent = np.frombuffer(buf, "<f4", 3, off + 0x100).copy()


class Node:
    def __init__(self, index, name, parent, local):
        self.index = index
        self.name = name
        self.parent = parent
        self.local = local
        self.children = []
        self.global_matrix = None
        self.inverse_bind = None


class MeshNode:
    def __init__(self, buf, off):
        self.obj = u32(buf, off)
        count = u32(buf, off + 0x04)
        self.node = u32(buf, off + 0x08)
        self.matrix = np.frombuffer(buf, "<f4", 16, off + 0x20).reshape(4, 4).copy()
        self.palette = list(struct.unpack_from("<%dI" % count, buf, off + 0x60))


class Tmc:
    def __init__(self, blob):
        if not blob.startswith(b"TMC\x00"):
            raise ValueError("not a TMC")
        self.buf = blob
        self.root = Block(blob, 0)
        self.name = cstr(blob, 0x50, 32)
        self.blocks = {}
        for off in self.root.entries():
            if off:
                block = Block(blob, off)
                self.blocks.setdefault(block.name, block)
        self.lheader = Layout(self.blocks["LHeader"])
        self.vtx = Layout(self.blocks["VtxLay"])
        self.idx = Layout(self.blocks["IdxLay"])
        ttdm = self.blocks.get("TTDM")
        self.ttdl = None
        if ttdm and ttdm.nested:
            nested = Block(blob, ttdm.off + ttdm.nested)
            if nested.name == "TTDL":
                self.ttdl = Layout(nested)
        self.objects = [ObjGeo(Block(blob, off)) for off in self.blocks["MdlGeo"].entries()]
        info = self.blocks.get("MdlInfo")
        self.bounds = [Bounds(blob, off) for off in info.entries()] if info else []
        self.materials = self._materials()
        self._read_nodes()

    @property
    def tmcl_size(self):
        return self.lheader.total

    def sections(self):
        """TMCL sections as {kind: (offset, size)}; LHeader sizes are padded, so match the closest fit."""
        out = {}
        wanted = {"TTDL": self.ttdl, "VtxLay": self.vtx, "IdxLay": self.idx}
        for offset, size in zip(self.lheader.offsets, self.lheader.sizes):
            fits = [(size - layout.total, kind) for kind, layout in wanted.items()
                    if layout is not None and kind not in out and 0 <= size - layout.total < 0x1000]
            if fits:
                out[min(fits)[1]] = (offset, size)
        return out

    def _materials(self):
        block = self.blocks.get("MtrCol")
        if not block:
            return []
        offsets = block.entries()
        ends = offsets[1:] + [block.off + block.size]
        out = []
        for off, end in zip(offsets, ends):
            rows = min(end - off, 0xD0) // 16
            colors = np.frombuffer(self.buf, "<f4", 4 * rows, off).reshape(rows, 4)
            out.append(colors[np.isfinite(colors).all(1) & (np.abs(colors) < 1e6).all(1)].copy())
        return out

    def _read_nodes(self):
        buf = self.buf
        names = []
        mesh_nodes = []
        for off in self.blocks["NodeLay"].entries():
            node_obj = Block(buf, off)
            names.append(cstr(buf, off + 0x50, 64))
            for sub in node_obj.entries():
                if sub:
                    mesh_nodes.append(MeshNode(buf, sub))
        self.mesh_nodes = {mesh.obj: mesh for mesh in mesh_nodes}
        hie = self.blocks["HieLay"].entries()
        glbl = self.blocks["GlblMtx"].entries()
        bnofs = self.blocks["BnOfsMtx"].entries()
        self.nodes = []
        for index, name in enumerate(names):
            off = hie[index]
            local = np.frombuffer(buf, "<f4", 16, off).reshape(4, 4).copy()
            node = Node(index, name, i32(buf, off + 0x40), local)
            node.global_matrix = np.frombuffer(buf, "<f4", 16, glbl[index]).reshape(4, 4).copy()
            node.inverse_bind = np.frombuffer(buf, "<f4", 16, bnofs[index]).reshape(4, 4).copy()
            self.nodes.append(node)
        for node in self.nodes:
            if 0 <= node.parent < len(self.nodes):
                self.nodes[node.parent].children.append(node.index)


class TmclView:
    """Slices of one inflated TMCL, addressed through a Tmc."""

    def __init__(self, tmc, blob):
        self.tmc = tmc
        self.blob = blob
        self.sections = tmc.sections()

    def check(self):
        """True if every section header in the TMCL matches the TMC layouts."""
        if len(self.blob) != self.tmc.tmcl_size:
            return False
        layouts = {"TTDL": self.tmc.ttdl, "VtxLay": self.tmc.vtx, "IdxLay": self.tmc.idx}
        for kind, (offset, _size) in self.sections.items():
            layout = layouts[kind]
            count, total = struct.unpack_from("<II", self.blob, offset)
            if count != layout.block.count or total != layout.total:
                return False
        return True

    def _slice(self, kind, layout, index):
        base = self.sections[kind][0]
        start = base + layout.offsets[index]
        return self.blob[start:start + layout.sizes[index]]

    def vertex_bytes(self, buffer):
        return self._slice("VtxLay", self.tmc.vtx, buffer)

    def index_array(self, buffer):
        return np.frombuffer(self._slice("IdxLay", self.tmc.idx, buffer), "<u2")

    def texture(self, index):
        return self._slice("TTDL", self.tmc.ttdl, index)

    def texture_count(self):
        return len(self.tmc.ttdl.offsets) if self.tmc.ttdl and "TTDL" in self.sections else 0

    def attributes(self, decl):
        """Decode one vertex buffer into {(usage_name, index): float/int array}."""
        raw = np.frombuffer(self.vertex_bytes(decl.buffer), np.uint8)
        count = len(raw) // decl.stride
        rows = raw[:count * decl.stride].reshape(count, decl.stride)
        out = {}
        for element in decl.elements:
            dtype, comps = ELEMENT_TYPES[element.type]
            width = np.dtype(dtype).itemsize * comps
            column = rows[:, element.offset:element.offset + width].copy().view(dtype).reshape(count, comps)
            out[(element.usage_name, element.index)] = column
        return out

    def bounds_match(self, tolerance=2e-3):
        """Compare decoded positions of object 0 with its MdlInfo bounding box."""
        tmc = self.tmc
        if not tmc.objects or not tmc.bounds or not tmc.objects[0].decls:
            return True
        positions = np.concatenate([self.attributes(decl)[("position", 0)][:, :3]
                                    for decl in tmc.objects[0].decls])
        lo, hi = positions.min(0), positions.max(0)
        if not np.isfinite(lo).all():
            return False
        bounds = tmc.bounds[0]
        return bool(np.allclose((lo + hi) / 2, bounds.center, atol=tolerance) and
                    np.allclose((hi - lo) / 2, bounds.extent, atol=tolerance))
