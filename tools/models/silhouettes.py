"""Renders the unit-marker silhouettes: for every model in mods/ww3mod/bits/models/ (not wrecks), a white
side view on transparency, front to the right, as <model>-icon.png beside it. The engine tints it
(UnitMarkerRenderable / MarkerIcons).

    blender --background --factory-startup --python tools/models/silhouettes.py -- [model ...]
"""

import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MODELS = os.path.join(ROOT, "mods", "ww3mod", "bits", "models")
W, H = 128, 48

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = args or sorted(f[:-4] for f in os.listdir(MODELS) if f.endswith(".glb") and not f.endswith("-wreck.glb"))

for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, name + ".glb"))
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH"]
    white = bpy.data.materials.new("white")
    white.use_nodes = True
    white.node_tree.nodes.clear()
    em = white.node_tree.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    out = white.node_tree.nodes.new("ShaderNodeOutputMaterial")
    white.node_tree.links.new(em.outputs[0], out.inputs["Surface"])
    pts = []
    for o in meshes:
        # The outline shell would fatten the silhouette: drop it.
        o.data.materials.clear()
        o.data.materials.append(white)
        pts += [o.matrix_world @ v.co for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    # Ortho scale spans the wider image side; fit both the length (y) and the height (z).
    cam.data.ortho_scale = max(hi.y - lo.y, (hi.z - lo.z) * W / H) * 1.04
    # From +X looking -X: +Y (the front) is to the right, +Z up.
    cam.location = (hi.x + 50, c.y, c.z)
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "CYCLES"
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 4
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = W, H
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = os.path.join(MODELS, name + "-icon.png")
    bpy.ops.render.render(write_still=True)
    print("icon", name)
