# -*- coding: utf-8 -*-
"""Render a front view of an exported .glb in Blender (background mode).

  blender -b -P tools\\blender_preview.py -- <out.png> <model.glb> [<model.glb> ...] [--show-brk] [--side]
                                         [--frame=N]

Objects whose name contains _brk (torn variants) are hidden unless --show-brk;
helper meshes (shadow proxies, sweat, face paint) are always hidden.
--head frames the camera on the face meshes only. --frame=N poses the imported
animation at scene frame N before rendering.
"""
import math
import sys

import bpy
from mathutils import Vector


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    flags = {arg for arg in args if arg.startswith("--")}
    png, glbs = args[0], [arg for arg in args[1:] if not arg.startswith("--")]
    show_brk = "--show-brk" in flags
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for glb in glbs:
        bpy.ops.import_scene.gltf(filepath=glb)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    helpers = ("SHADOW_MODEL", "zdmodel", "sweat", "face_paint")
    for obj in meshes:
        if (not show_brk and "_brk" in obj.name) or any(h in obj.name for h in helpers):
            obj.hide_render = True
    visible = [obj for obj in meshes if not obj.hide_render]
    if "--head" in flags:
        visible = [obj for obj in visible if "face" in obj.name] or visible
    frame = next((int(arg.split("=", 1)[1]) for arg in flags if arg.startswith("--frame=")), None)
    if frame is not None:
        bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    corners = []
    for obj in visible:
        evaluated = obj.evaluated_get(depsgraph)
        corners.extend(evaluated.matrix_world @ v.co for v in evaluated.to_mesh().vertices)
        evaluated.to_mesh_clear()
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center, size = (lo + hi) / 2, max(hi - lo)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {
        item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 900, 1200
    scene.render.filepath = png
    world = bpy.data.worlds.new("world")
    world.color = (0.6, 0.6, 0.65)
    scene.world = world

    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = size * 1.1
    if "--side" in flags:
        camera.location = center + Vector((size * 3, 0, 0))
        camera.rotation_euler = (math.radians(90), 0, math.radians(90))
    else:
        camera.location = center + Vector((0, -size * 3, 0))
        camera.rotation_euler = (math.radians(90), 0, 0)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for angle, energy in ((0, 3.0), (150, 1.5), (-150, 1.5)):
        light = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
        light.data.energy = energy
        light.rotation_euler = (math.radians(70), 0, math.radians(angle))
        scene.collection.objects.link(light)
    bpy.ops.render.render(write_still=True)
    print("rendered", png, "objects", len(visible), "of", len(meshes))


main()
