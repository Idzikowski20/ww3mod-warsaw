"""Facade texture library for the 3D Warsaw map, rendered in Blender (run inside Blender 5.x).

Each style is a real facade panel built as geometry (recessed windows, frames, sills, cornices, balconies)
with dirty post-war materials (soot, rain streaks under sills, rising damp, patched plaster), lit like an
overcast day and rendered orthographically, face-on. The renders are made seamless and packed into an
atlas by build_city.py; the engine tiles them along walls in metres, so one panel covers every building of
that style.

A style renders two tiles:
  upper   2 bays x 2 floors, repeats horizontally and vertically
  ground  2 bays x the ground-floor height, repeats horizontally

Usage inside Blender:  exec(open(r"<this file>").read()); render_style("kamienica", out_dir)
or render_all(out_dir).
"""
import math
import os
import random

import bmesh
import bpy

TILE_PX = 1024

# width per bay, upper floor height, ground floor height (metres) and the look of each style.
STYLES = {
    "kamienica": dict(bay=3.4, floor=3.6, ground=4.6, wall=(0.58, 0.54, 0.47), war=1.0, win=(1.3, 2.0), sill=1.0,
                      cornice=True, pilasters=True, balcony=False, panels=False, curtain=False, dirt=1.0,
                      shop=True),
    "socrealizm": dict(bay=3.0, floor=3.4, ground=5.0, wall=(0.70, 0.64, 0.52), war=0.3, win=(1.2, 1.9), sill=1.0,
                       cornice=True, pilasters=True, balcony=False, panels=False, curtain=False, dirt=0.8,
                       shop=True, arcade=True),
    "plyta": dict(bay=3.6, floor=2.8, ground=3.0, wall=(0.58, 0.58, 0.56), win=(1.5, 1.5), sill=0.9,
                  cornice=False, pilasters=False, balcony=True, panels=True, curtain=False, dirt=0.9,
                  shop=False),
    "biurowiec": dict(bay=1.5, floor=3.5, ground=5.0, wall=(0.45, 0.46, 0.47), win=(1.3, 2.3), sill=0.6,
                      cornice=False, pilasters=False, balcony=False, panels=False, curtain=True, dirt=0.6,
                      shop=False, glass=(0.10, 0.13, 0.15)),
    "szklo": dict(bay=1.6, floor=3.8, ground=6.0, wall=(0.30, 0.34, 0.37), win=(1.5, 3.5), sill=0.1,
                  cornice=False, pilasters=False, balcony=False, panels=False, curtain=True, dirt=0.25,
                  shop=False, glass=(0.12, 0.20, 0.26)),
    "pawilon": dict(bay=4.0, floor=3.6, ground=4.0, wall=(0.55, 0.53, 0.50), win=(3.2, 2.4), sill=0.4,
                    cornice=False, pilasters=False, balcony=False, panels=True, curtain=False, dirt=1.0,
                    shop=True),
    "cegla": dict(bay=3.0, floor=3.2, ground=3.2, wall=(0.42, 0.24, 0.18), war=0.6, win=(1.0, 1.4), sill=1.1,
                  cornice=False, pilasters=False, balcony=False, panels=False, curtain=False, dirt=1.2,
                  shop=False, brick=True),
    "piaskowiec": dict(bay=2.6, floor=3.6, ground=5.0, wall=(0.66, 0.60, 0.49), war=0.3, win=(1.0, 2.1), sill=1.0,
                       cornice=True, pilasters=True, balcony=False, panels=False, curtain=False, dirt=0.9,
                       shop=False),
}

BAYS = 2


# --- Scene ------------------------------------------------------------------------------------------
def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def set_engine(scene):
    for engine in ("CYCLES",):
        try:
            scene.render.engine = engine
        except TypeError:
            pass
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    try:
        scene.cycles.device = "GPU"
    except TypeError:
        pass
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = False


def lin(c):
    """Style colours are written as sRGB (what you would pick from a photo); Blender shades in linear."""
    return tuple(x ** 2.2 for x in c)


def world_overcast(scene, strength=0.45):
    world = bpy.data.worlds.get("Overcast") or bpy.data.worlds.new("Overcast")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    bg = next(n for n in nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.80, 0.83, 1.0)
    bg.inputs[1].default_value = strength
    scene.world = world


def add_sun():
    # Low enough from the upper left that window reveals, sills and cornices throw readable shadows.
    data = bpy.data.lights.new("Sun", "SUN")
    data.energy = 3.0
    data.angle = math.radians(6)
    sun = bpy.data.objects.new("Sun", data)
    sun.rotation_euler = (math.radians(40), math.radians(-35), 0)
    bpy.context.scene.collection.objects.link(sun)


def add_camera(width, height):
    data = bpy.data.cameras.new("FacadeCam")
    data.type = "ORTHO"
    data.ortho_scale = max(width, height)
    cam = bpy.data.objects.new("FacadeCam", data)
    cam.location = (width / 2, -20.0, height / 2)
    cam.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.collection.objects.link(cam)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = TILE_PX if width >= height else int(TILE_PX * width / height)
    scene.render.resolution_y = TILE_PX if height >= width else int(TILE_PX * height / width)
    scene.render.resolution_percentage = 100


# --- Materials -------------------------------------------------------------------------------------
def _node(nodes, kind):
    return nodes.new(kind)


def dirty_material(name, colour, dirt, brick=False, roughness=0.9, war=0.0):
    """Plaster/stone/concrete with soot, rain streaks and rising damp, all procedural in object space.
    `war` > 0 adds post-war damage: plaster flaked off down to the brick, and shrapnel pockmarks."""
    colour = lin(colour)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = roughness

    coord = _node(nodes, "ShaderNodeTexCoord")
    sep = _node(nodes, "ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Object"], sep.inputs[0])

    # Large blotchy discolouration (patched, repainted plaster).
    blotch = _node(nodes, "ShaderNodeTexNoise")
    blotch.inputs["Scale"].default_value = 0.35
    blotch.inputs["Detail"].default_value = 6.0
    links.new(coord.outputs["Object"], blotch.inputs["Vector"])

    # Vertical rain streaks: noise stretched along z.
    stretch = _node(nodes, "ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = (1.6, 1.0, 0.12)
    links.new(coord.outputs["Object"], stretch.inputs["Vector"])
    streak = _node(nodes, "ShaderNodeTexNoise")
    streak.inputs["Scale"].default_value = 1.8
    streak.inputs["Detail"].default_value = 3.0
    links.new(stretch.outputs[0], streak.inputs["Vector"])

    # Fine grit.
    grit = _node(nodes, "ShaderNodeTexNoise")
    grit.inputs["Scale"].default_value = 40.0
    grit.inputs["Detail"].default_value = 2.0
    links.new(coord.outputs["Object"], grit.inputs["Vector"])

    base = _node(nodes, "ShaderNodeRGB")
    base.outputs[0].default_value = (*colour, 1.0)
    base_out = base.outputs[0]

    def mix(a, b, fac, blend="MULTIPLY"):
        m = _node(nodes, "ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = blend
        colours = [i for i in m.inputs if i.type == "RGBA"]
        links.new(fac, next(i for i in m.inputs if i.type == "VALUE"))
        links.new(a, colours[0])
        links.new(b, colours[1])
        return next(o for o in m.outputs if o.type == "RGBA")

    soot = _node(nodes, "ShaderNodeRGB")
    soot.outputs[0].default_value = (*lin((0.16, 0.15, 0.13)), 1.0)

    if war > 0:
        # Flaked plaster: where a large noise crosses a threshold the wall shows brick underneath.
        flake = _node(nodes, "ShaderNodeTexNoise")
        flake.inputs["Scale"].default_value = 0.9
        flake.inputs["Detail"].default_value = 8.0
        flake.inputs["Roughness"].default_value = 0.7
        links.new(coord.outputs["Object"], flake.inputs["Vector"])
        flake_mask = _node(nodes, "ShaderNodeMapRange")
        flake_mask.inputs["From Min"].default_value = 0.64 - 0.08 * war
        flake_mask.inputs["From Max"].default_value = 0.66 - 0.08 * war
        links.new(flake.outputs["Fac"], flake_mask.inputs["Value"])
        under = _node(nodes, "ShaderNodeTexBrick")
        under.inputs["Scale"].default_value = 4.0
        under.inputs["Mortar Size"].default_value = 0.015
        under.inputs["Color1"].default_value = (*lin((0.45, 0.25, 0.18)), 1.0)
        under.inputs["Color2"].default_value = (*lin((0.36, 0.20, 0.15)), 1.0)
        under.inputs["Mortar"].default_value = (*lin((0.50, 0.47, 0.42)), 1.0)
        links.new(coord.outputs["Object"], under.inputs["Vector"])
        m = _node(nodes, "ShaderNodeMix")
        m.data_type = "RGBA"
        cols = [i for i in m.inputs if i.type == "RGBA"]
        links.new(flake_mask.outputs["Result"], next(i for i in m.inputs if i.type == "VALUE"))
        links.new(base_out, cols[0])
        links.new(under.outputs["Color"], cols[1])
        base_out = next(o for o in m.outputs if o.type == "RGBA")

        # Shrapnel pockmarks: small dark voronoi pits.
        pits = _node(nodes, "ShaderNodeTexVoronoi")
        pits.feature = "F1"
        pits.inputs["Scale"].default_value = 9.0
        links.new(coord.outputs["Object"], pits.inputs["Vector"])
        pit_mask = _node(nodes, "ShaderNodeMapRange")
        pit_mask.inputs["From Min"].default_value = 0.13
        pit_mask.inputs["From Max"].default_value = 0.02
        pit_mask.inputs["To Max"].default_value = 0.7 * war
        links.new(pits.outputs["Distance"], pit_mask.inputs["Value"])
        pit_noise = _node(nodes, "ShaderNodeTexNoise")
        pit_noise.inputs["Scale"].default_value = 0.6
        links.new(coord.outputs["Object"], pit_noise.inputs["Vector"])
        pit_gate = _node(nodes, "ShaderNodeMapRange")
        pit_gate.inputs["From Min"].default_value = 0.42
        pit_gate.inputs["From Max"].default_value = 0.52
        links.new(pit_noise.outputs["Fac"], pit_gate.inputs["Value"])
        pit_amt = _node(nodes, "ShaderNodeMath")
        pit_amt.operation = "MULTIPLY"
        links.new(pit_mask.outputs["Result"], pit_amt.inputs[0])
        links.new(pit_gate.outputs["Result"], pit_amt.inputs[1])
        m2 = _node(nodes, "ShaderNodeMix")
        m2.data_type = "RGBA"
        cols2 = [i for i in m2.inputs if i.type == "RGBA"]
        links.new(pit_amt.outputs[0], next(i for i in m2.inputs if i.type == "VALUE"))
        links.new(base_out, cols2[0])
        links.new(soot.outputs[0], cols2[1])
        base_out = next(o for o in m2.outputs if o.type == "RGBA")

    ramp_b = _node(nodes, "ShaderNodeValToRGB")
    ramp_b.color_ramp.elements[0].position = 0.30
    ramp_b.color_ramp.elements[1].position = 0.70
    links.new(blotch.outputs["Fac"], ramp_b.inputs["Fac"])
    scale_b = _node(nodes, "ShaderNodeMath")
    scale_b.operation = "MULTIPLY"
    scale_b.inputs[1].default_value = 0.60 * dirt
    links.new(ramp_b.outputs["Color"], scale_b.inputs[0])
    col = mix(base_out, soot.outputs[0], scale_b.outputs[0], "MIX")

    ramp_s = _node(nodes, "ShaderNodeValToRGB")
    ramp_s.color_ramp.elements[0].position = 0.45
    ramp_s.color_ramp.elements[1].position = 0.70
    links.new(streak.outputs["Fac"], ramp_s.inputs["Fac"])
    scale_s = _node(nodes, "ShaderNodeMath")
    scale_s.operation = "MULTIPLY"
    scale_s.inputs[1].default_value = 0.35 * dirt
    links.new(ramp_s.outputs["Color"], scale_s.inputs[0])
    col = mix(col, soot.outputs[0], scale_s.outputs[0], "MIX")

    # Rising damp: darker in the first ~1.2 m of the panel bottom.
    damp = _node(nodes, "ShaderNodeMapRange")
    damp.inputs["From Min"].default_value = 1.4
    damp.inputs["From Max"].default_value = 0.0
    damp.inputs["To Max"].default_value = 0.35 * dirt
    links.new(sep.outputs["Z"], damp.inputs["Value"])
    col = mix(col, soot.outputs[0], damp.outputs["Result"], "MIX")

    grit_amt = _node(nodes, "ShaderNodeMath")
    grit_amt.operation = "MULTIPLY"
    grit_amt.inputs[1].default_value = 0.25
    links.new(grit.outputs["Fac"], grit_amt.inputs[0])
    col = mix(col, soot.outputs[0], grit_amt.outputs[0], "MIX")

    if brick:
        bricks = _node(nodes, "ShaderNodeTexBrick")
        bricks.inputs["Scale"].default_value = 4.0
        bricks.inputs["Mortar Size"].default_value = 0.012
        bricks.inputs["Color1"].default_value = (*colour, 1.0)
        bricks.inputs["Color2"].default_value = (colour[0] * 0.8, colour[1] * 0.8, colour[2] * 0.8, 1.0)
        bricks.inputs["Mortar"].default_value = (*lin((0.45, 0.42, 0.38)), 1.0)
        links.new(coord.outputs["Object"], bricks.inputs["Vector"])
        col = mix(bricks.outputs["Color"], col, scale_b.outputs[0], "MULTIPLY")

    links.new(col, bsdf.inputs["Base Color"])
    return mat


def glass_material(name, colour=(0.08, 0.10, 0.12)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin(colour), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Metallic"].default_value = 0.3
    return mat


def window_glass(seed, base):
    """Per-window variety: dark interiors of different depth, some with net curtains, a few boarded up."""
    rnd = random.Random(seed)
    roll = rnd.random()
    if roll < 0.18:
        return plain_material(f"Curtain{seed}", (0.46, 0.43, 0.36), 0.9)
    if roll < 0.23:
        return plain_material(f"Board{seed}", (0.30, 0.24, 0.18), 0.95)
    k = 0.6 + 0.8 * rnd.random()
    return glass_material(f"Glass{seed}", tuple(min(c * k, 1.0) for c in base))


def plain_material(name, colour, roughness=0.7, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin(colour), 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


# --- Geometry --------------------------------------------------------------------------------------
def box(name, x0, x1, y0, y1, z0, z1, mat):
    """Axis-aligned box; y is depth (negative = towards the camera)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def wall_with_openings(width, height, openings, mat, glasses, depth=0.25):
    """A wall slab from x=0..width, z=0..height with rectangular window openings recessed by `depth`.
    The opening reveals use the wall material; each opening's pane (glasses[k]) sits at the back."""
    mesh = bpy.data.meshes.new("Wall")
    bm = bmesh.new()
    # Build the face of the wall as a grid split along every opening edge, then drop the opening cells.
    xs = sorted({0.0, width, *[o[0] for o in openings], *[o[1] for o in openings]})
    zs = sorted({0.0, height, *[o[2] for o in openings], *[o[3] for o in openings]})

    def is_opening(cx, cz):
        return any(o[0] <= cx <= o[1] and o[2] <= cz <= o[3] for o in openings)

    vert = {}

    def v(x, z):
        key = (round(x, 4), round(z, 4))
        if key not in vert:
            vert[key] = bm.verts.new((x, 0.0, z))
        return vert[key]

    for i in range(len(xs) - 1):
        for k in range(len(zs) - 1):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[k] + zs[k + 1]) / 2
            if is_opening(cx, cz):
                continue
            bm.faces.new((v(xs[i], zs[k]), v(xs[i + 1], zs[k]), v(xs[i + 1], zs[k + 1]), v(xs[i], zs[k + 1])))
    # Reveals (inner sides of each opening) and the glass pane at the back.
    for k, (x0, x1, z0, z1) in enumerate(openings):
        for a, b in (((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))):
            p = bm.verts.new((a[0], 0.0, a[1]))
            q = bm.verts.new((b[0], 0.0, b[1]))
            r = bm.verts.new((b[0], depth, b[1]))
            s = bm.verts.new((a[0], depth, a[1]))
            bm.faces.new((p, q, r, s))
        g = bm.faces.new((bm.verts.new((x0, depth, z0)), bm.verts.new((x1, depth, z0)),
                          bm.verts.new((x1, depth, z1)), bm.verts.new((x0, depth, z1))))
        g.material_index = 1 + k
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Wall", mesh)
    obj.data.materials.append(mat)
    for glass in glasses:
        obj.data.materials.append(glass)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def window_frames(x0, x1, z0, z1, mat, depth=0.2, bar=0.06, mullions=1, transom=True):
    """Window frame bars set just in front of the glass."""
    y0, y1 = depth - 0.06, depth - 0.01
    box("Frame", x0, x1, y0, y1, z0, z0 + bar, mat)
    box("Frame", x0, x1, y0, y1, z1 - bar, z1, mat)
    box("Frame", x0, x0 + bar, y0, y1, z0, z1, mat)
    box("Frame", x1 - bar, x1, y0, y1, z0, z1, mat)
    for m in range(1, mullions + 1):
        cx = x0 + (x1 - x0) * m / (mullions + 1)
        box("Frame", cx - bar / 2, cx + bar / 2, y0, y1, z0, z1, mat)
    if transom:
        tz = z0 + (z1 - z0) * 0.72
        box("Frame", x0, x1, y0, y1, tz - bar / 2, tz + bar / 2, mat)


# --- Panels --------------------------------------------------------------------------------------
def build_upper(s, seed):
    random.seed(seed)
    width, height = s["bay"] * BAYS, s["floor"] * 2
    wall = dirty_material("Wall", s["wall"], s["dirt"], brick=s.get("brick", False), war=s.get("war", 0.0))
    glass_base = s.get("glass", (0.07, 0.09, 0.11))
    frame = plain_material("Frame", (0.32, 0.30, 0.27) if not s["curtain"] else (0.38, 0.40, 0.42), 0.6,
                           0.5 if s["curtain"] else 0.0)
    stone = dirty_material("Stone", tuple(c * 1.08 for c in s["wall"]), s["dirt"] * 0.8)

    ww, wh = s["win"]
    openings = []
    for f in range(2):
        for b in range(BAYS):
            cx = (b + 0.5) * s["bay"]
            z0 = f * s["floor"] + s["sill"]
            if s["curtain"]:
                z0 = f * s["floor"] + (s["floor"] - wh) / 2
            openings.append((cx - ww / 2, cx + ww / 2, z0, min(z0 + wh, (f + 1) * s["floor"] - 0.15)))
    if s["curtain"]:
        glasses = [glass_material(f"Glass{k}", tuple(c * (0.85 + 0.3 * random.random()) for c in glass_base))
                   for k in range(len(openings))]
    else:
        glasses = [window_glass(seed * 100 + k, glass_base) for k in range(len(openings))]
    wall_with_openings(width, height, openings, wall, glasses, depth=0.12 if s["curtain"] else 0.25)

    for x0, x1, z0, z1 in openings:
        if s["curtain"]:
            window_frames(x0, x1, z0, z1, frame, depth=0.12, bar=0.05, mullions=0, transom=False)
            continue
        window_frames(x0, x1, z0, z1, frame, mullions=1, transom=True)
        box("Sill", x0 - 0.08, x1 + 0.08, -0.12, 0.05, z0 - 0.06, z0, stone)
        if s["cornice"]:
            box("Lintel", x0 - 0.12, x1 + 0.12, -0.08, 0.0, z1 + 0.05, z1 + 0.30, stone)

    if s["curtain"]:
        # Floor spandrels and vertical fins of a curtain wall.
        for f in range(3):
            box("Spandrel", 0, width, -0.06, 0.0, f * s["floor"] - 0.25, f * s["floor"] + 0.25, frame)
        for b in range(BAYS + 1):
            box("Fin", b * s["bay"] - 0.05, b * s["bay"] + 0.05, -0.18, 0.0, 0, height, frame)
    if s["cornice"]:
        for f in range(3):
            box("Cornice", 0, width, -0.14, 0.0, f * s["floor"] - 0.10, f * s["floor"] + 0.12, stone)
    if s["pilasters"]:
        for b in range(BAYS + 1):
            box("Pilaster", b * s["bay"] - 0.22, b * s["bay"] + 0.22, -0.06, 0.0, 0, height, stone)
    if s["panels"]:
        joint = plain_material("Joint", (0.25, 0.25, 0.24), 0.9)
        for f in range(3):
            box("JointH", 0, width, -0.01, 0.0, f * s["floor"] - 0.02, f * s["floor"] + 0.02, joint)
        for b in range(BAYS + 1):
            box("JointV", b * s["bay"] - 0.02, b * s["bay"] + 0.02, -0.01, 0.0, 0, height, joint)
    if s["balcony"]:
        rail = dirty_material("Rail", (0.50, 0.50, 0.48), s["dirt"])
        for f in range(2):
            b = (f + seed) % BAYS
            x0, x1 = b * s["bay"] + 0.1, (b + 1) * s["bay"] - 0.1
            z = f * s["floor"]
            box("Slab", x0, x1, -1.1, 0.0, z + 0.05, z + 0.20, rail)
            box("Parapet", x0, x1, -1.1, -1.0, z + 0.20, z + 1.10, rail)
    return width, height


def build_ground(s, seed):
    random.seed(seed + 1)
    width, height = s["bay"] * BAYS, s["ground"]
    wall = dirty_material("WallG", tuple(c * 0.92 for c in s["wall"]), s["dirt"] * 1.3, brick=s.get("brick", False),
                          war=s.get("war", 0.0))
    glass_base = s.get("glass", (0.06, 0.07, 0.08))
    frame = plain_material("FrameG", (0.22, 0.22, 0.22), 0.5, 0.4)
    openings = []
    for b in range(BAYS):
        cx = (b + 0.5) * s["bay"]
        if s.get("shop"):
            w = min(s["bay"] - 0.6, 2.8)
            openings.append((cx - w / 2, cx + w / 2, 0.45, min(height - 0.8, 3.3)))
        elif s["curtain"]:
            openings.append((cx - s["bay"] * 0.45, cx + s["bay"] * 0.45, 0.1, height - 0.6))
        else:
            w = s["win"][0]
            openings.append((cx - w / 2, cx + w / 2, 1.0, 1.0 + s["win"][1]))
    glasses = [glass_material(f"GlassG{k}", tuple(c * (0.8 + 0.4 * random.random()) for c in glass_base))
               for k in range(len(openings))]
    wall_with_openings(width, height, openings, wall, glasses, depth=0.3)
    for x0, x1, z0, z1 in openings:
        window_frames(x0, x1, z0, z1, frame, depth=0.3, bar=0.07, mullions=1, transom=s.get("shop", False))
    if s.get("shop"):
        sign = plain_material("Sign", (0.30, 0.28, 0.26), 0.8)
        box("Fascia", 0, width, -0.10, 0.0, height - 0.75, height - 0.35, sign)
    if s.get("arcade"):
        stone = dirty_material("Rust", tuple(c * 1.05 for c in s["wall"]), s["dirt"])
        # Rusticated bands only on the wall above the shop windows, never across the glass.
        top = max(o[3] for o in openings)
        for k in range(int(height / 0.5)):
            z = k * 0.5
            if z > top + 0.1:
                box("Rustic", 0, width, -0.04, 0.0, z, z + 0.03, stone)
    return width, height


def render_panel(build, s, seed, path):
    reset_scene()
    scene = bpy.context.scene
    set_engine(scene)
    world_overcast(scene)
    add_sun()
    width, height = build(s, seed)
    add_camera(width, height)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return width, height


def render_style(name, out_dir, seed=7):
    s = STYLES[name]
    os.makedirs(out_dir, exist_ok=True)
    wu, hu = render_panel(build_upper, s, seed, os.path.join(out_dir, f"{name}_upper.png"))
    wg, hg = render_panel(build_ground, s, seed, os.path.join(out_dir, f"{name}_ground.png"))
    return {"name": name, "width": wu, "upper": hu, "ground": hg}


def render_all(out_dir):
    return [render_style(n, out_dir) for n in STYLES]
