# -*- coding: utf-8 -*-
"""Dump a RenderDoc capture into readable files for analysing the game's renderer.

  python tools\\rdc_dump.py renderdoc\\misaki.rdc [--out DIR] [--no-textures] [--no-targets]
                            [--events FIRST-LAST] [--timeout SECONDS]

Runs itself inside qrenderdoc.exe (its embedded Python has the renderdoc module) and
only reads the capture. qrenderdoc gets the arguments through an environment variable
and exits when the script ends, also on errors (see dump.log). --events limits the
per-draw dump to a range of event ids, for a quick check.
Writes out\\renderdoc\\<capture name>\\:
  passes.csv      draws grouped by render target set (the game has no debug markers)
  actions.csv     one row per action: event, pass, index count, shaders, bound textures
  shaders\\       <stage>_<hash>.txt: reflection (cbuffers, textures, samplers, signatures)
                  and DXBC disassembly; hash = md5 of the bytecode, stable across captures
  draws\\         <event>.json: pipeline state, cbuffer variables, textures, samplers
  textures.csv    every texture: id, name, size, format, and whether it is a render target
  textures\\      <id>.png of every texture a shader reads (mip 0, slice 0); .dds with every mip and
                  slice for float / cube / array textures
  buffers\\       <id>.bin + .json of every buffer a shader reads, at its first use (stride, members)
  targets\\       <pass>_<id>.png of each pass's render targets after its last draw
                  (.exr as well for float targets)
"""
import csv
import hashlib
import json
import os
import struct
import subprocess
import sys
import traceback

QRENDERDOC = r"C:\Program Files\RenderDoc\qrenderdoc.exe"
ENV_ARGS = "RDC_DUMP_ARGS"


class Args:
    def __init__(self, values):
        self.__dict__.update(values)


def launch(argv):
    """Outside RenderDoc: re-run this file under qrenderdoc, wait, and print its log."""
    import argparse
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("capture")
    ap.add_argument("--out")
    ap.add_argument("--no-textures", action="store_true")
    ap.add_argument("--no-targets", action="store_true")
    ap.add_argument("--events", help="FIRST-LAST event ids to dump per draw")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)
    capture = os.path.abspath(args.capture)
    out = os.path.abspath(args.out or os.path.join(
        repo, "out", "renderdoc", os.path.splitext(os.path.basename(capture))[0]))
    first, last = 0, 1 << 31
    if args.events:
        first, last = (int(x) for x in args.events.split("-"))
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "dump.log")
    if os.path.exists(log):
        os.remove(log)
    env = dict(os.environ)
    env[ENV_ARGS] = json.dumps({"capture": capture, "out": out, "no_textures": args.no_textures,
                                "no_targets": args.no_targets, "first": first, "last": last})
    proc = subprocess.Popen([QRENDERDOC, "--python", os.path.abspath(__file__)], env=env)
    try:
        code = proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("timed out after %d s, qrenderdoc %d killed" % (args.timeout, proc.pid))
        code = 1
    if os.path.exists(log):
        with open(log, encoding="utf-8") as fh:
            sys.stdout.write(fh.read())
    else:
        print("no dump.log: the script did not start inside qrenderdoc")
    return code


# ---------------------------------------------------------------- inside qrenderdoc

class Dumper:
    def __init__(self, rd, ctrl, args, log):
        self.rd, self.ctrl, self.args, self.log = rd, ctrl, args, log
        self.sf = ctrl.GetStructuredFile()
        self.textures = {t.resourceId: t for t in ctrl.GetTextures()}
        self.names = {r.resourceId: r.name for r in ctrl.GetResources()}
        self.shader_files = {}       # shader id -> file stem
        self.view_format = {}        # texture id -> a view format seen on it (for typeless casts)
        self.read_textures = set()
        self.render_targets = set()
        self.state_error = False
        self.saved_buffers = set()
        self.current_event = 0

    # ---- helpers
    def rid(self, resource_id):
        return int(resource_id)

    def null(self, resource_id):
        return resource_id == self.rd.ResourceId.Null()

    def tex_desc(self, resource_id):
        t = self.textures.get(resource_id)
        if t is None:
            return self.names.get(resource_id, "buffer %d" % self.rid(resource_id))
        size = "%dx%d" % (t.width, t.height)
        if t.depth > 1:
            size += "x%d" % t.depth
        if t.arraysize > 1:
            size += "[%d]" % t.arraysize
        return "%d %s %s" % (self.rid(resource_id), size, t.format.Name())

    def leaves(self):
        out = []

        def walk(actions):
            for a in actions:
                if a.children:
                    walk(a.children)
                else:
                    out.append(a)
        walk(self.ctrl.GetRootActions())
        return out

    def stages(self):
        S = self.rd.ShaderStage
        return [("vs", S.Vertex), ("hs", S.Hull), ("ds", S.Domain), ("gs", S.Geometry), ("ps", S.Pixel),
                ("cs", S.Compute)]

    # ---- shaders
    def shader_file(self, pipe, stage_name, stage):
        shader = pipe.GetShader(stage)
        if self.null(shader):
            return None
        if shader in self.shader_files:
            return self.shader_files[shader]
        refl = pipe.GetShaderReflection(stage)
        digest = hashlib.md5(bytes(refl.rawBytes)).hexdigest()[:12] if refl else "id%d" % self.rid(shader)
        stem = "%s_%s" % (stage_name, digest)
        self.shader_files[shader] = stem
        path = os.path.join(self.args.out, "shaders", stem + ".txt")
        if not os.path.exists(path):
            lines = ["shader %s  resource %d  entry %s" % (stem, self.rid(shader), pipe.GetShaderEntryPoint(stage))]
            if refl:
                lines += self.reflection_text(refl)
                pipeline = pipe.GetComputePipelineObject() if stage_name == "cs" else pipe.GetGraphicsPipelineObject()
                try:
                    lines += ["", "---- DXBC", self.ctrl.DisassembleShader(pipeline, refl, "DXBC")]
                except Exception as exc:  # noqa: BLE001
                    lines.append("disassembly failed: %s" % exc)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        return stem

    def type_name(self, var):
        t = var.type
        name = t.name
        if t.elements > 1:
            name += "[%d]" % t.elements
        return name

    def variable_lines(self, variables, indent, base=0):
        lines = []
        for v in variables:
            lines.append("%s%4d  %-12s %s" % (indent, base + v.byteOffset, self.type_name(v), v.name))
            if v.type.members:
                lines += self.variable_lines(v.type.members, indent + "    ", base + v.byteOffset)
        return lines

    def reflection_text(self, refl):
        lines = ["", "---- constant buffers"]
        for c in refl.constantBlocks:
            lines.append("b%d  %s  %d bytes" % (c.fixedBindNumber, c.name, c.byteSize))
            lines += self.variable_lines(c.variables, "    ")
        lines.append("")
        lines.append("---- textures / buffers")
        for r in refl.readOnlyResources:
            lines.append("t%d  %s  %s" % (r.fixedBindNumber, r.name, str(r.textureType).split(".")[-1]))
        for r in refl.readWriteResources:
            lines.append("u%d  %s  %s" % (r.fixedBindNumber, r.name, str(r.textureType).split(".")[-1]))
        lines.append("")
        lines.append("---- samplers")
        for s in refl.samplers:
            lines.append("s%d  %s" % (s.fixedBindNumber, s.name))
        for title, sig in (("inputs", refl.inputSignature), ("outputs", refl.outputSignature)):
            lines.append("")
            lines.append("---- " + title)
            for p in sig:
                lines.append("%s%d  reg %d  %s x%d" % (p.semanticName, p.semanticIndex, p.regIndex,
                                                        str(p.varType).split(".")[-1], p.compCount))
        return lines

    # ---- cbuffer values
    def values(self, var):
        if var.members:
            if all(m.name.startswith("[") for m in var.members):
                return [self.values(m) for m in var.members]
            return {m.name: self.values(m) for m in var.members}
        n = max(1, var.rows * var.columns)
        kind = str(var.type).split(".")[-1]
        if kind in ("SInt", "SShort", "SByte"):
            vals = list(var.value.s32v[:n])
        elif kind in ("UInt", "UShort", "UByte", "Bool"):
            vals = list(var.value.u32v[:n])
        else:
            vals = [round(float(x), 6) for x in var.value.f32v[:n]]
        return vals[0] if n == 1 else vals

    def constant_buffers(self, pipe, stage_name, stage):
        refl = pipe.GetShaderReflection(stage)
        if refl is None:
            return []
        shader = pipe.GetShader(stage)
        pipeline = pipe.GetComputePipelineObject() if stage_name == "cs" else pipe.GetGraphicsPipelineObject()
        out = []
        for used in pipe.GetConstantBlocks(stage, True):
            index = used.access.index
            if index >= len(refl.constantBlocks):
                continue
            block = refl.constantBlocks[index]
            d = used.descriptor
            entry = {"slot": block.fixedBindNumber, "name": block.name, "buffer": self.rid(d.resource),
                     "offset": d.byteOffset, "size": block.byteSize}
            try:
                variables = self.ctrl.GetCBufferVariableContents(
                    pipeline, shader, stage, pipe.GetShaderEntryPoint(stage), index, d.resource, d.byteOffset,
                    block.byteSize)
                entry["values"] = {v.name: self.values(v) for v in variables}
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)
                if not self.null(d.resource):
                    raw = self.ctrl.GetBufferData(d.resource, d.byteOffset, block.byteSize)
                    entry["raw"] = [round(x, 6) for x in struct.unpack("<%df" % (len(raw) // 4), raw)]
            out.append(entry)
        return out

    def bound_textures(self, pipe, stage_name, stage):
        refl = pipe.GetShaderReflection(stage)
        out = []
        for used in pipe.GetReadOnlyResources(stage, True):
            d = used.descriptor
            if self.null(d.resource):
                continue
            name, slot = "", -1
            if refl and used.access.index < len(refl.readOnlyResources):
                r = refl.readOnlyResources[used.access.index]
                name, slot = r.name, r.fixedBindNumber
            if d.resource in self.textures:
                self.read_textures.add(d.resource)
                self.view_format.setdefault(d.resource, d.format)
            else:
                self.save_buffer(d, name, refl.readOnlyResources[used.access.index] if name else None, stage_name)
            out.append({"slot": slot, "name": name, "resource": self.rid(d.resource),
                        "desc": self.tex_desc(d.resource), "view_format": d.format.Name()})
        return out

    def save_buffer(self, d, name, res, stage_name):
        """buffers\\<id>.bin at its first use (contents can change later in the frame) + .json"""
        rid = self.rid(d.resource)
        if rid in self.saved_buffers:
            return
        self.saved_buffers.add(rid)
        stride = 0
        try:
            stride = res.variableType.arrayByteStride if res is not None else 0
        except Exception:  # noqa: BLE001
            pass
        size = getattr(d, "byteSize", 0)
        data = bytes(self.ctrl.GetBufferData(d.resource, d.byteOffset, size if size and size < (1 << 40) else 0))
        path = os.path.join(self.args.out, "buffers", "%d" % rid)
        with open(path + ".bin", "wb") as fh:
            fh.write(data)
        meta = {"resource": rid, "name": name, "stage": stage_name, "event": self.current_event,
                "offset": d.byteOffset, "bytes": len(data), "stride": stride, "format": d.format.Name(),
                "members": []}
        try:
            for m in res.variableType.members:
                meta["members"].append({"name": m.name, "offset": m.byteOffset, "type": self.type_name(m)})
        except Exception:  # noqa: BLE001
            pass
        with open(path + ".json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)

    def samplers(self, pipe, stage):
        refl = pipe.GetShaderReflection(stage)
        out = []
        for used in pipe.GetSamplers(stage, True):
            s = used.sampler
            slot = -1
            if refl and used.access.index < len(refl.samplers):
                slot = refl.samplers[used.access.index].fixedBindNumber
            out.append({"slot": slot, "filter": str(s.filter.minify).split(".")[-1] + "/" +
                        str(s.filter.mip).split(".")[-1] + "/" + str(s.filter.filter).split(".")[-1],
                        "address": [str(a).split(".")[-1] for a in (s.addressU, s.addressV, s.addressW)],
                        "compare": str(s.compareFunction).split(".")[-1], "anisotropy": s.maxAnisotropy})
        return out

    def fixed_state(self, st):
        om, rs = st.outputMerger, st.rasterizer.state
        ds = om.depthStencilState
        blends = []
        for b in om.blendState.blends:
            blends.append({"enabled": b.enabled, "color": "%s %s %s" % (
                str(b.colorBlend.source).split(".")[-1], str(b.colorBlend.operation).split(".")[-1],
                str(b.colorBlend.destination).split(".")[-1]), "alpha": "%s %s %s" % (
                str(b.alphaBlend.source).split(".")[-1], str(b.alphaBlend.operation).split(".")[-1],
                str(b.alphaBlend.destination).split(".")[-1]), "write": b.writeMask})

        def face(f):
            name = lambda v: str(v).split(".")[-1]
            return {"func": name(f.function), "pass": name(f.passOperation), "fail": name(f.failOperation),
                    "depth_fail": name(f.depthFailOperation), "read_mask": f.compareMask,
                    "write_mask": f.writeMask}
        return {
            "depth": {"test": ds.depthEnable, "write": ds.depthWrites,
                      "func": str(ds.depthFunction).split(".")[-1], "stencil": ds.stencilEnable,
                      "stencil_ref": ds.frontFace.reference,
                      "stencil_front": face(ds.frontFace), "stencil_back": face(ds.backFace)},
            "raster": {"cull": str(rs.cullMode).split(".")[-1], "front_ccw": rs.frontCCW,
                       "fill": str(rs.fillMode).split(".")[-1], "depth_bias": rs.depthBias,
                       "slope_bias": rs.slopeScaledDepthBias},
            "blend": blends[:max(1, len([v for v in om.renderTargets if not self.null(v.resource)]))],
        }

    # ---- main walk
    def run(self):
        out = self.args.out
        for sub in ("shaders", "draws", "textures", "targets", "buffers"):
            os.makedirs(os.path.join(out, sub), exist_ok=True)
        rd = self.rd
        F = rd.ActionFlags
        rows, passes = [], []
        leaves = self.leaves()
        self.log("actions %d" % len(leaves))
        for n, a in enumerate(leaves):
            if n % 200 == 0:
                self.log("  %d / %d" % (n, len(leaves)))
            name = a.GetName(self.sf)
            is_draw = bool(a.flags & F.Drawcall)
            is_dispatch = bool(a.flags & F.Dispatch)
            row = {"event": a.eventId, "pass": "", "name": name, "indices": a.numIndices,
                   "instances": a.numInstances, "index_offset": a.indexOffset, "base_vertex": a.baseVertex,
                   "vertex_offset": a.vertexOffset}
            if not (is_draw or is_dispatch) or not (self.args.first <= a.eventId <= self.args.last):
                rows.append(row)
                continue
            self.ctrl.SetFrameEvent(a.eventId, False)
            self.current_event = a.eventId
            pipe = self.ctrl.GetPipelineState()
            st = self.ctrl.GetD3D11PipelineState()
            rts = [v for v in st.outputMerger.renderTargets if not self.null(v.resource)]
            depth = st.outputMerger.depthTarget
            for v in rts + ([depth] if not self.null(depth.resource) else []):
                self.render_targets.add(v.resource)
                self.view_format.setdefault(v.resource, v.format)
            key = (tuple(self.rid(v.resource) for v in rts), self.rid(depth.resource), is_dispatch)
            if not passes or passes[-1]["key"] != key:
                passes.append({"key": key, "index": len(passes), "first": a.eventId, "last": a.eventId,
                               "draws": 0, "ps": set(), "kind": "compute" if is_dispatch else "draw",
                               "targets": [self.tex_desc(v.resource) for v in rts],
                               "target_ids": [v.resource for v in rts],
                               "depth": self.tex_desc(depth.resource) if not self.null(depth.resource) else "",
                               "depth_id": depth.resource})
            p = passes[-1]
            p["last"] = a.eventId
            p["draws"] += 1
            row["pass"] = p["index"]
            draw = {"event": a.eventId, "name": name, "pass": p["index"], "indices": a.numIndices,
                    "instances": a.numInstances, "targets": p["targets"], "depth_target": p["depth"],
                    "stages": {}}
            for stage_name, stage in self.stages():
                stem = self.shader_file(pipe, stage_name, stage)
                if not stem:
                    continue
                row[stage_name] = stem
                draw["stages"][stage_name] = {
                    "shader": stem,
                    "cbuffers": self.constant_buffers(pipe, stage_name, stage),
                    "textures": self.bound_textures(pipe, stage_name, stage),
                    "samplers": self.samplers(pipe, stage),
                }
                if stage_name == "ps":
                    p["ps"].add(stem)
                row[stage_name + "_textures"] = " ".join(
                    "t%d:%d" % (t["slot"], t["resource"]) for t in draw["stages"][stage_name]["textures"])
            if is_draw:
                try:
                    draw["state"] = self.fixed_state(st)
                except Exception as exc:  # noqa: BLE001
                    if not self.state_error:
                        self.log("fixed state: %s" % traceback.format_exc())
                    self.state_error = True
                    draw["state"] = {"error": str(exc), "raster": {"cull": ""}, "depth": {"write": ""}, "blend": []}
                draw["inputs"] = [{"name": i.name, "format": i.format.Name(), "offset": i.byteOffset,
                                   "buffer": i.vertexBuffer} for i in pipe.GetVertexInputs() if i.used]
                ib = pipe.GetIBuffer()
                draw["index_buffer"] = {"resource": self.rid(ib.resourceId), "offset": ib.byteOffset,
                                        "stride": ib.byteStride}
                draw["topology"] = str(pipe.GetPrimitiveTopology()).split(".")[-1]
                row["cull"] = draw["state"]["raster"]["cull"]
                row["depth_write"] = draw["state"]["depth"]["write"]
                row["blend"] = draw["state"]["blend"][0]["enabled"] if draw["state"]["blend"] else False
            with open(os.path.join(out, "draws", "%d.json" % a.eventId), "w", encoding="utf-8") as fh:
                json.dump(draw, fh, ensure_ascii=False, indent=1)
            rows.append(row)

        self.write_csv("actions.csv", rows, ["event", "pass", "name", "indices", "instances", "index_offset",
                                             "base_vertex", "vertex_offset", "vs", "hs", "ds", "gs", "ps", "cs",
                                             "cull", "depth_write", "blend", "vs_textures", "ps_textures",
                                             "cs_textures"])
        self.write_csv("passes.csv", [{
            "pass": p["index"], "kind": p["kind"], "first": p["first"], "last": p["last"], "draws": p["draws"],
            "pixel_shaders": " ".join(sorted(p["ps"])), "targets": " | ".join(p["targets"]), "depth": p["depth"],
        } for p in passes], ["pass", "kind", "first", "last", "draws", "pixel_shaders", "targets", "depth"])
        self.write_textures_csv()
        if not self.args.no_targets:
            self.save_targets(passes)
        if not self.args.no_textures:
            self.save_read_textures()
        self.log("done: %d passes, %d shaders, %d textures read" % (
            len(passes), len(self.shader_files), len(self.read_textures)))

    def write_csv(self, name, rows, fields):
        with open(os.path.join(self.args.out, name), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        self.log("wrote %s %d" % (name, len(rows)))

    def write_textures_csv(self):
        rows = []
        for rid, t in sorted(self.textures.items(), key=lambda kv: int(kv[0])):
            rows.append({"id": int(rid), "name": self.names.get(rid, ""), "width": t.width, "height": t.height,
                         "depth": t.depth, "mips": t.mips, "array": t.arraysize, "cube": t.cubemap,
                         "format": t.format.Name(), "render_target": rid in self.render_targets,
                         "read": rid in self.read_textures})
        self.write_csv("textures.csv", rows, ["id", "name", "width", "height", "depth", "mips", "array", "cube",
                                              "format", "render_target", "read"])

    # ---- saving images
    def is_float(self, fmt):
        name = fmt.Name()
        return "FLOAT" in name or "R11G11B10" in name or name.startswith("R16G16B16A16") and "UNORM" not in name

    def save(self, resource_id, path, file_type):
        rd = self.rd
        ts = rd.TextureSave()
        ts.resourceId = resource_id
        ts.destType = file_type
        all_subresources = file_type == rd.FileType.DDS  # DDS keeps every mip and cube face
        ts.mip = -1 if all_subresources else 0
        ts.slice.sliceIndex = -1 if all_subresources else 0
        ts.alpha = rd.AlphaMapping.Preserve
        view = self.view_format.get(resource_id)
        tex = self.textures[resource_id]
        if "TYPELESS" in tex.format.Name():
            if "D24" in tex.format.Name() or "D32" in tex.format.Name():
                ts.typeCast = rd.CompType.Depth
            elif view is not None:
                ts.typeCast = view.compType
        result = self.ctrl.SaveTexture(ts, path)
        ok = getattr(result, "OK", lambda: bool(result))()
        if not ok:
            self.log("  save failed %s: %s" % (os.path.basename(path), getattr(result, "Message", lambda: "")()))

    def save_targets(self, passes):
        rd = self.rd
        self.log("saving pass targets")
        for p in passes:
            if p["kind"] != "draw":
                continue
            self.ctrl.SetFrameEvent(p["last"], True)
            ids = list(p["target_ids"]) + ([p["depth_id"]] if not self.null(p["depth_id"]) else [])
            for k, rid in enumerate(ids):
                if rid not in self.textures:
                    continue
                kind = "depth" if k == len(p["target_ids"]) else "rt%d" % k
                stem = os.path.join(self.args.out, "targets", "p%02d_%s_%d" % (p["index"], kind, self.rid(rid)))
                self.save(rid, stem + ".png", rd.FileType.PNG)
                view = self.view_format.get(rid)
                if kind != "depth" and view is not None and self.is_float(view):
                    self.save(rid, stem + ".exr", rd.FileType.EXR)

    def save_read_textures(self):
        rd = self.rd
        self.log("saving %d read textures" % len(self.read_textures))
        last = self.leaves()[-1].eventId
        self.ctrl.SetFrameEvent(last, True)
        for rid in sorted(self.read_textures, key=int):
            if rid in self.render_targets:
                continue  # contents change during the frame; see targets\
            tex = self.textures[rid]
            stem = os.path.join(self.args.out, "textures", "%d" % self.rid(rid))
            self.save(rid, stem + ".png", rd.FileType.PNG)
            if tex.cubemap or tex.arraysize > 1 or self.is_float(tex.format):
                self.save(rid, stem + ".dds", rd.FileType.DDS)


def run_inside():
    args = Args(json.loads(os.environ[ENV_ARGS]))
    os.makedirs(args.out, exist_ok=True)
    log_file = open(os.path.join(args.out, "dump.log"), "w", encoding="utf-8")

    def log(text):
        log_file.write(text + "\n")
        log_file.flush()

    log("started inside qrenderdoc, python %s" % sys.version.split()[0])
    try:
        import renderdoc as rd
        cap = rd.OpenCaptureFile()
        result = cap.OpenFile(args.capture, "", None)
        if not result.OK():
            raise RuntimeError("cannot open %s: %s" % (args.capture, result.Message()))
        result, ctrl = cap.OpenCapture(rd.ReplayOptions(), None)
        if not result.OK():
            raise RuntimeError("cannot replay: %s" % result.Message())
        log("capture %s  api %s" % (args.capture, ctrl.GetAPIProperties().pipelineType))
        Dumper(rd, ctrl, args, log).run()
        ctrl.Shutdown()
        cap.Shutdown()
    except Exception:  # noqa: BLE001
        log(traceback.format_exc())
    log_file.close()


# qrenderdoc runs this file without __file__ and maybe under another __name__,
# so the inside branch only looks at the environment.
if ENV_ARGS in os.environ:
    try:
        run_inside()
    finally:
        os._exit(0)  # leave qrenderdoc without opening its window, also after errors
elif __name__ == "__main__":
    sys.exit(launch(sys.argv[1:]))
