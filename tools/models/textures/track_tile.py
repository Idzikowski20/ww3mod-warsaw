"""Renders track_tile.png: exactly two link pitches of straight track, outer face seen square-on, lit flat
(the material's albedo as emission: the engine lights it), u across the belt, v along it. Seamless along v.
Source: "Animated Tank Tracks Rig" by Patrik, BlenderKit, Royalty Free (tools/models/wiring/tracks-credits.md).

    blender --background --factory-startup WORKSPACE/m4-refs/sources/blenderkit-tank-tracks/animated_tank_tracks_rig_1K.blend \
        --python tools/models/textures/track_tile.py
"""
import os
import bpy

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track_tile.png")
W_PX, H_PX = 128, 256
scene = bpy.context.scene
links = [bpy.data.objects["L_Tracks"], bpy.data.objects["L_TracksJoints"]]
for o in scene.objects:
    o.hide_render = o not in links


def evaluated(o):
    bpy.context.view_layer.update()
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [e.matrix_world @ v.co for v in e.data.vertices]


# Straight: no curve. The link pitch is how far the second array copy reaches past the first.
for o in links:
    o.modifiers.remove(o.modifiers["Curve"])
o = links[0]
o.modifiers["Array"].count = 1
one = max(v.y for v in evaluated(o))
o.modifiers["Array"].count = 2
pitch = max(v.y for v in evaluated(o)) - one
for o in links:
    o.modifiers["Array"].count = 14
pts = [v for o in links for v in evaluated(o)]
x0, x1 = min(v.x for v in pts), max(v.x for v in pts)
y0, y1 = min(v.y for v in pts), max(v.y for v in pts)
width = x1 - x0

m = bpy.data.materials["Dirty Tracks"]
nt = m.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
emit = nt.nodes.new("ShaderNodeEmission")
nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, emit.inputs["Color"])
nt.links.new(emit.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output).inputs["Surface"])

world = bpy.data.worlds.new("tile")
world.use_nodes = True
next(n for n in world.node_tree.nodes if n.type == "BACKGROUND").inputs["Color"].default_value = (0.02, 0.02, 0.018, 1)
scene.world = world

# The straight piece's +z side is the outer face (it faces the ground on the rig's bottom run). Looking down,
# image up is +y: along the belt.
cam = bpy.data.objects.new("tile", bpy.data.cameras.new("tile"))
scene.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = width
cam.location = ((x0 + x1) / 2, (y0 + y1) / 2, max(v.z for v in pts) + 2)
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.device = "CPU"
scene.render.resolution_x, scene.render.resolution_y = W_PX, H_PX
scene.render.resolution_percentage = 100
# Non-square pixels: the width spans the belt, the height exactly two pitches.
scene.render.pixel_aspect_x = width / (2 * pitch) * H_PX / W_PX
scene.render.pixel_aspect_y = 1
# Display values (sRGB, no tone curve), stored as they are: the engine shows texture values unconverted.
# The Raw view would store the linear values, near black (mean 0.09) once shown as display values.
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"track tile: pitch {pitch:.4f} m, width {width:.3f} m -> {OUT}")
