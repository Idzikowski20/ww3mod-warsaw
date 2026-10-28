"""Shared parts for the defence and base-building models (CRAM, AGUN, SAM, HSAM, GTWR, PBOX, HBOX, GUN, FTUR,
MSLO, HPAD, LOGISTICSCENTER, AFLD, SUPPLYROUTE, walls, fences and gates).

- fit(): turns, scales and grounds a downloaded mesh and returns the source -> model point mapping, so cut
  lines and pivots can be measured in the source. (Works round convert.normalize, whose "+X"/"-X" fronts
  are swapped: Matrix.Rotation(-90 deg) turns a +X nose to -Y.)
- crop(): cuts a mesh to a box (bisect, UVs kept) - to take one piece out of a big source.
- prop(): the sandbags, concrete blocks, tyres and HESCO bastions of the Military/Urban Prop Set
  (2M triangles), imported once, decimated and cached as a .blend in the temp folder.
- hand-built helpers: sandbag rows, camo netting, concrete pads, base furniture, fences, gates.
No player colour on these models: the unit marker shows the side (user decision).
"""

import math
import os
import random
import tempfile

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import convert  # noqa: F401  (also used by the wall modules as D.convert)
from lib import box, cyl, extrude, join, mat, prism

PROPSET = "militaryurban_prop_set_sandbag_tire_concreteblock_sandbox.glb"
CACHE = os.path.join(tempfile.gettempdir(), "ww3mod_defence_props_v2.blend")

CONCRETE = (0.46, 0.45, 0.42)
CONCRETE_DARK = (0.33, 0.32, 0.3)
EARTH = (0.33, 0.27, 0.19)
STEEL = (0.3, 0.31, 0.3)
OLIVE = (0.27, 0.29, 0.18)
RUST = (0.32, 0.2, 0.12)
WOOD = (0.36, 0.26, 0.16)
BLACK = (0.05, 0.05, 0.05)
YELLOW = (0.75, 0.6, 0.12)
NET = ((0.22, 0.25, 0.14), (0.3, 0.27, 0.17), (0.16, 0.18, 0.11))


# --- downloaded meshes ---------------------------------------------------------------------------

def fit(o, rot=0.0, k=1.0, centre=None, floor=None, lift=0.0):
    """Bakes into o's mesh: a turn of rot degrees counter-clockwise about Z (nose +X -> 90, -X -> -90,
    -Y -> 180), a scale by k, the bbox (or the source point centre) centred on x/y and its lowest point
    (or the source height floor) put on z = 0. Returns p(x, y, z): source point -> model point."""
    r = Matrix.Rotation(math.radians(rot), 4, "Z")
    pts = [r @ v.co for v in o.data.vertices]
    if centre is None:
        cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2
        cy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
    else:
        c = r @ Vector(centre)
        cx, cy = c.x, c.y
    cz = min(p.z for p in pts) if floor is None else floor
    m = Matrix.Translation((0, 0, lift)) @ Matrix.Scale(k, 4) @ Matrix.Translation((-cx, -cy, -cz)) @ r
    o.data.transform(m)
    lo, hi = convert.bounds(o)
    print(f"fit {o.name}: x {lo.x:.2f}..{hi.x:.2f}  y {lo.y:.2f}..{hi.y:.2f}  z {lo.z:.2f}..{hi.z:.2f}")
    inv = m.inverted()

    def p(x, y, z):
        return tuple(m @ Vector((x, y, z)))
    p.src = lambda c: inv @ Vector(c)  # model point -> source point, for split rules written in the source
    return p


def crop(o, lo, hi):
    """Cuts o's mesh to the box lo..hi (model metres, None = open side); faces across a side are cut."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for axis in range(3):
        for bound, sign in ((lo[axis], -1), (hi[axis], 1)):
            if bound is None:
                continue
            co = Vector((0, 0, 0))
            co[axis] = bound
            no = Vector((0, 0, 0))
            no[axis] = sign
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, dist=1e-5)
    bm.to_mesh(o.data)
    bm.free()


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def transform(o, loc=(0, 0, 0), rot=0.0, scale=1.0, tilt=(0.0, 0.0)):
    """Moves a prop copy: scale, tilt (x, y degrees), turn rot degrees about Z, then to loc."""
    m = (Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rot), 4, "Z")
         @ Matrix.Rotation(math.radians(tilt[1]), 4, "Y") @ Matrix.Rotation(math.radians(tilt[0]), 4, "X")
         @ (Matrix.Scale(scale, 4) if not isinstance(scale, tuple) else
            Matrix.Diagonal((*scale, 1))))
    o.data.transform(m)
    return o


# --- the prop set, cached ------------------------------------------------------------------------

# name: (source objects, triangle target). Each is centred on x/y and stood on z = 0, real size.
PROPS = {
    "sandbag": (["sand_bag_mesh_sand_bag_0"], 900),
    "block": (["road_concrete_block_mesh_road_concrete_b"], 260),
    "tyre": (["tire_mesh_tire_0"], 220),
    "tyre_flat": (["tire_mesh.004_tire_0"], 180),
}


def _build_cache():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(convert.SOURCES, PROPSET))
    new = [o for o in bpy.data.objects if o not in before]
    dg = bpy.context.evaluated_depsgraph_get()
    flat = {}
    for o in new:
        if o.type != "MESH":
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        flat[o.name] = me
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    out = []
    for name, (sources, target) in PROPS.items():
        parts = []
        for s in sources:
            key = next(k for k in flat if k.startswith(s))
            p = bpy.data.objects.new(name, flat[key].copy())
            bpy.context.scene.collection.objects.link(p)
            parts.append(p)
        convert._join(parts)
        p = parts[0]
        p.name = "prop_" + name
        p.data.name = "prop_" + name
        convert.decimate(p, target)
        lo, hi = convert.bounds(p)
        p.data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
        out.append(p)
    for me in flat.values():
        bpy.data.meshes.remove(me)
    for img in bpy.data.images:
        if img.has_data and not img.packed_file:
            img.pack()
    bpy.data.libraries.write(CACHE, set(out), fake_user=True)
    for p in out:
        bpy.data.objects.remove(p, do_unlink=True)


def prop(name, loc=(0, 0, 0), rot=0.0, scale=1.0, tilt=(0.0, 0.0), parent=None):
    """A fresh copy of a prop-set piece (see PROPS), moved into place. Real size: sandbag pile 2.1 x 1.3 x
    0.6 m, concrete block 1.2 x 0.5 x 0.6 m, tyre 0.8 m. (The set's HESCO bastion does not survive decimation:
    hesco() builds them by hand.)"""
    if not os.path.exists(CACHE):
        _build_cache()
    key = "prop_" + name
    if key not in bpy.data.objects:
        with bpy.data.libraries.load(CACHE, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n == key]
    base = bpy.data.objects[key]
    o = bpy.data.objects.new(name, base.data.copy())
    bpy.context.scene.collection.objects.link(o)
    transform(o, loc, rot, scale, tilt)
    raw_textures(o)
    if parent:
        o.parent = parent
    return o


# --- hand-built parts ----------------------------------------------------------------------------

def sandbag_row(start, end, layers=2, parent=None, jitter=0.0, seed=1):
    """Sandbag piles from start to end (x, y, z), the prop set's pile repeated along the line; layers
    stacks them (each pile is about 0.6 m tall, the next layer set back a little and offset half a pile)."""
    random.seed(seed)
    s, e = Vector(start), Vector(end)
    d = e - s
    length = d.length
    yaw = math.degrees(math.atan2(d.y, d.x)) - 90  # pile's long axis is x: turn so it runs along d
    n = max(1, round(length / 1.95))
    step = length / n
    out = []
    for layer in range(layers):
        z = s.z + layer * 0.5
        shift = (step / 2) if layer % 2 else 0
        for i in range(n + (1 if layer % 2 else 0) - (1 if layer % 2 else 0)):
            t = (i + 0.5) * step + shift - (step / 2 if layer % 2 else 0)
            if layer % 2 and (t < step * 0.4 or t > length - step * 0.4):
                continue
            p = s + d.normalized() * t
            out.append(prop("sandbag", (p.x, p.y, z), yaw + 90 + random.uniform(-jitter, jitter),
                            (step / 2.1, 1.0, 1.0), parent=parent))
    return out


def camo_net(name, size, loc, height=2.5, droop=1.6, poles=True, seed=3, parent=None, res=18, holes=0.0):
    """Camouflage netting: a sheet of size (x, y) held up at height over loc on poles, sagging between them,
    its edges drooping droop metres toward the ground, garnished in blotches of three greens and browns.
    holes (0..1) tears that share of it away (wrecks). Returns the net."""
    random.seed(seed)
    mats = [mat(f"net{i}", c) for i, c in enumerate(NET)]
    bm = bmesh.new()
    nx, ny = res, max(2, round(res * size[1] / size[0]))
    grid = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            u, v = i / nx * 2 - 1, j / ny * 2 - 1
            edge = max(abs(u), abs(v))
            fall = max(0.0, edge - 0.55) / 0.45
            z = height - droop * fall ** 1.6
            # Sag between the poles (at u, v = +-0.84) and lumps of garnish.
            z -= 0.35 * (1 - fall) * (math.cos(u * math.pi / 0.84 * 0.5) ** 2 + math.cos(v * math.pi / 0.84 * 0.5) ** 2) / 2
            z += 0.18 * noise.noise(Vector((u * 4.1 + seed, v * 4.1, 0.5)))
            grid[i, j] = bm.verts.new((u * size[0] / 2, v * size[1] / 2, max(0.05, z)))
    for i in range(nx):
        for j in range(ny):
            if holes and random.random() < holes:
                continue
            f = bm.faces.new((grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
            c = f.calc_center_median()
            n = noise.noise(Vector((c.x * 0.9 + seed, c.y * 0.9, 1.7))) + 0.3 * noise.noise(Vector((c.x * 3, c.y * 3, 4.2)))
            f.material_index = 0 if n < -0.15 else 1 if n < 0.2 else 2
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for m in mats:
        me.materials.append(m)
    # Two-sided: a thin solidify so the net shows from below and gets an outline.
    mod = o.modifiers.new("thick", "SOLIDIFY")
    mod.thickness = 0.06
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    o.location = loc
    if parent:
        o.parent = parent

    if poles:
        st = mat("wood", WOOD)
        for sx in (-0.42, 0.42):
            for sy in (-0.42, 0.42):
                cyl("net_pole", 0.05, height + 0.15, (loc[0] + sx * size[0], loc[1] + sy * size[1], loc[2] + (height + 0.15) / 2),
                    st, segments=5, parent=parent)
    return o


def pad(name, size, loc=(0, 0, 0), height=0.25, material=None, parent=None, bevel=0.05):
    """A cast concrete slab of size (x, y), its top at loc z + height."""
    return box(name, (size[0], size[1], height), (loc[0], loc[1], loc[2] + height / 2),
               material or mat("concrete", CONCRETE), bevel=bevel, parent=parent)


def berm(name, outer, inner, height, loc=(0, 0, 0), material=None, parent=None, segments=24):
    """An earth ring: a sloped bank round an ellipse, outer (rx, ry) at the ground, inner (rx, ry) at the top."""
    bm = bmesh.new()
    ring = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        c, s = math.cos(a), math.sin(a)
        wob = 1 + 0.06 * noise.noise(Vector((c * 2, s * 2, 0.3)))
        ring.append((
            bm.verts.new((outer[0] * c * wob, outer[1] * s * wob, 0)),
            bm.verts.new(((outer[0] + inner[0]) / 2 * c * wob, (outer[1] + inner[1]) / 2 * s * wob, height)),
            bm.verts.new((inner[0] * c * wob, inner[1] * s * wob, height * 0.85)),
            bm.verts.new((inner[0] * 0.92 * c * wob, inner[1] * 0.92 * s * wob, 0.0)),
        ))
    for i in range(segments):
        a, b = ring[i], ring[(i + 1) % segments]
        for k in range(3):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material or mat("earth", EARTH))
    o.location = loc
    if parent:
        o.parent = parent
    return o


def shard_scatter(n, area, z=0.0, size=(0.3, 0.9), material=None, seed=7, parent=None, name="rubble"):
    """Broken concrete lumps scattered over area (x0, y0, x1, y1): wreck rubble."""
    random.seed(seed)
    m = material or mat("concrete_dark", CONCRETE_DARK)
    out = []
    for i in range(n):
        s = random.uniform(*size)
        o = box(name, (s, s * random.uniform(0.6, 1.3), s * random.uniform(0.3, 0.7)),
                (random.uniform(area[0], area[2]), random.uniform(area[1], area[3]), z + s * 0.2),
                m, rot=(random.uniform(-25, 25), random.uniform(-25, 25), random.uniform(0, 180)), parent=parent)
        out.append(o)
    return out


HESCO = (0.52, 0.48, 0.36)


def hesco(start, end, height=1.37, cell=1.06, parent=None, name="hesco"):
    """A HESCO bastion line (wire-mesh gabions lined with geotextile, filled with earth) from start to end
    (x, y, z ground points): one cell every 1.06 m, each a slightly bulging fabric box in a welded-mesh cage."""
    s, e = Vector(start), Vector(end)
    d = e - s
    n = max(1, round(d.length / cell))
    step = d.length / n
    yaw = math.degrees(math.atan2(d.y, d.x))
    fabric = mat("hesco", HESCO)
    wire = mat("hesco_wire", (0.22, 0.22, 0.2))
    soil = mat("earth", EARTH)
    out = []
    for i in range(n):
        p = s + d.normalized() * (i + 0.5) * step
        c = box(name, (step * 0.98, cell * 0.98, height), (p.x, p.y, s.z + height / 2), fabric, bevel=0.06,
                rot=(0, 0, yaw), parent=parent)
        out.append(c)
        out.append(box(name + "_soil", (step * 0.9, cell * 0.9, 0.04), (p.x, p.y, s.z + height - 0.03), soil,
                       rot=(0, 0, yaw), parent=parent))
        for band in (0.25, 0.62, 1.0):  # the cage's horizontal wires, as dark bands round the cell
            out.append(box(name + "_band", (step * 1.0, cell * 1.0, 0.035), (p.x, p.y, s.z + height * band), wire,
                           rot=(0, 0, yaw), parent=parent))
    return out


def paint(o, colours, default=None):
    """Sets the flat base colour of o's untextured materials: colours {material name: rgb}, default for the
    rest (None leaves them). For sources whose paint is too dark or wrong for the real thing."""
    for m in o.data.materials:
        if m is None or not m.use_nodes:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None or bsdf.inputs["Base Color"].is_linked:
            continue
        rgb = colours.get(m.name.split(".0")[0] if m.name not in colours else m.name, default)
        if rgb is not None:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1)
            m.diffuse_color = (*rgb, 1)


def raw_textures(o):
    """Marks o's source textures Non-Color, so the bake carries their authored values as they are. Read as
    sRGB they are linearised first and come out far darker than the source looks (the engine and the
    preview show texture values raw, with no gamma step)."""
    for m in o.data.materials:
        if m is None or not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                n.image.colorspace_settings.name = "Non-Color"


def done(root):
    """Ends a build(): refreshes every object's world matrix before lib.finish() merges the parts (it reads
    matrix_world, which is stale for parts made since the last scene update: they would land at the origin)."""
    bpy.context.view_layer.update()
    return root


def mound(name, size, height, loc=(0, 0, 0), top=0.35, material=None, parent=None, seed=5):
    """A heap of earth: an irregular octagon of size (x, y) at the ground narrowing to top x that at height."""
    random.seed(seed)
    poly = []
    for i in range(8):
        a = 2 * math.pi * (i + 0.5) / 8
        r = random.uniform(0.85, 1.05)
        poly.append((math.cos(a) * size[0] / 2 * r, math.sin(a) * size[1] / 2 * r))
    return extrude(name, poly, height, loc, material or mat("earth", EARTH), top_scale=top, parent=parent)


# --- base furniture ------------------------------------------------------------------------------

def container(name, loc, rot=0.0, colour=(0.28, 0.3, 0.2), parent=None):
    """A 20 ft ISO container (6.06 x 2.44 x 2.59 m), corrugated sides, doors at its -x end, its long axis
    along x before rot (degrees)."""
    body = mat("container_" + "%.2f%.2f%.2f" % colour, colour)
    rib = mat("container_rib_" + "%.2f%.2f%.2f" % colour, tuple(c * 0.75 for c in colour))
    x, y, z = loc
    parts = [box(name, (6.06, 2.44, 2.59), (0, 0, 1.295), body, bevel=0.03)]
    for i in range(9):  # corrugations
        for side in (-1, 1):
            parts.append(box(name + "_rib", (0.12, 0.04, 2.3), (-2.6 + i * 0.65, side * 1.23, 1.3), rib))
    parts.append(box(name + "_doors", (0.04, 2.3, 2.4), (-3.04, 0, 1.3), rib))
    for dy in (-0.55, 0.55):
        parts.append(box(name + "_bar", (0.06, 0.05, 2.3), (-3.07, dy, 1.3), mat("steel", STEEL)))
    o = join(parts[0], *parts[1:])
    o.data.transform(Matrix.Rotation(math.radians(rot), 4, "Z"))
    o.location = (x, y, z)
    if parent:
        o.parent = parent
    return o


def shelter(name, size, loc, rot=0.0, colour=(0.42, 0.4, 0.3), parent=None, segments=8, open_front=True):
    """An arched fabric maintenance shelter (size x wide, y deep, its half-round roof the height), on a
    steel frame, open at its +y end (before rot), as field workshops use."""
    w, d = size
    r = w / 2
    fabric = mat("fabric_" + "%.2f%.2f%.2f" % colour, colour)
    frame = mat("steel", STEEL)
    profile_out, profile_in = [], []
    for i in range(segments + 1):
        a = math.pi * i / segments
        profile_out.append((math.cos(a) * r, math.sin(a) * r * 0.85 + 0.4))
    # The roof as a thin shell: outer arch out, inner arch back.
    poly = profile_out + [(x * 0.96, (z - 0.4) * 0.96 + 0.4) for x, z in reversed(profile_out)]
    roof = prism(name, [(x, z) for x, z in poly], d, material=fabric, axis="Y")
    parts = [roof]
    for k in range(5):  # frame hoops
        yk = -d / 2 + k * d / 4
        for i in range(segments):
            a0, a1 = profile_out[i], profile_out[i + 1]
            mx, mz = (a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2
            ln = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
            ang = math.degrees(math.atan2(a1[1] - a0[1], a1[0] - a0[0]))
            parts.append(box(name + "_hoop", (ln, 0.1, 0.1), (mx * 1.01, yk, mz * 1.0 + 0.02), frame, rot=(0, -ang, 0)))
    for side in (-1, 1):
        parts.append(box(name + "_wall", (0.06, d, 0.45), (side * r * 0.99, 0, 0.22), fabric))
    if not open_front:
        parts.append(box(name + "_end", (w * 0.95, 0.06, r * 0.85 + 0.3), (0, d / 2, (r * 0.85 + 0.3) / 2), fabric))
    parts.append(box(name + "_back", (w * 0.95, 0.06, r * 0.85 + 0.3), (0, -d / 2, (r * 0.85 + 0.3) / 2), fabric))
    o = join(parts[0], *parts[1:])
    o.data.transform(Matrix.Rotation(math.radians(rot), 4, "Z"))
    o.location = loc
    if parent:
        o.parent = parent
    return o


def bladder(name, size, loc, parent=None):
    """A collapsible fuel bladder (pillow tank) of size (x, y), 0.8 m high when full, with its fill hose."""
    w, d = size
    rubber = mat("bladder", (0.12, 0.13, 0.1))
    o = box(name, (w, d, 0.8), (loc[0], loc[1], loc[2] + 0.38), rubber, bevel=0.32, taper=(0.9, 0.9))
    cyl(name + "_valve", 0.15, 0.25, (loc[0] + w / 2 - 0.2, loc[1], loc[2] + 0.8), mat("steel", STEEL),
        segments=8, parent=parent)
    if parent:
        o.parent = parent
    return o


def crates(name, loc, n=4, rot=0.0, parent=None, seed=11):
    """A pallet of olive ammunition boxes, n of them stacked."""
    random.seed(seed)
    wood = mat("pallet", WOOD)
    olive = mat("crate", (0.29, 0.31, 0.19))
    x, y, z = loc
    parts = [box(name, (1.2, 1.0, 0.14), (0, 0, 0.07), wood)]
    for i in range(n):
        parts.append(box(name + "_box", (0.55, 0.45, 0.32), ((i % 2) * 0.58 - 0.29, ((i // 2) % 2) * 0.48 - 0.24,
                                                               0.3 + (i // 4) * 0.33), olive, bevel=0.02))
    o = join(parts[0], *parts[1:])
    o.data.transform(Matrix.Rotation(math.radians(rot), 4, "Z"))
    o.location = (x, y, z)
    if parent:
        o.parent = parent
    return o


def jersey(loc, rot=0.0, parent=None):
    """A concrete jersey barrier (3 x 0.7 x 0.8 m): the prop set's road block scaled to the real thing."""
    return prop("block", loc, rot, (2.5, 1.35, 1.35), parent=parent)


def bay_lines(name, size, loc, parent=None, colour=YELLOW):
    """Painted bay outline of size (x, y) on the ground at loc."""
    m = mat("paint_" + "%.2f" % colour[0], colour)
    w, d = size
    x, y, z = loc
    out = []
    for dx, dy, sx, sy in ((0, d / 2, w, 0.15), (0, -d / 2, w, 0.15), (w / 2, 0, 0.15, d), (-w / 2, 0, 0.15, d)):
        out.append(box(name, (sx, sy, 0.02), (x + dx, y + dy, z + 0.01), m, parent=parent))
    return out


# --- walls, fences, gates ------------------------------------------------------------------------
# Walls connect to their neighbours in game: each is a <unit>-post at the origin and a <unit>-segment that
# runs one cell (4 m of model at Scale 2) along +y from it, to the next cell's post.

CELL = 4.0
WALL_SOURCE = "concrete_wall_protection.glb"


def torus(name, major, minor, loc, rot=(0, 0, 0), material=None, seg=10, seg2=3, parent=None):
    """A ring (a coil of wire, seen as rings): major radius, wire radius minor, in the xz plane before rot."""
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        c = Vector((math.cos(a) * major, 0, math.sin(a) * major))
        n = Vector((math.cos(a), 0, math.sin(a)))
        rings.append([bm.verts.new(c + (n * math.cos(2 * math.pi * j / seg2) + Vector((0, 1, 0)) *
                                        math.sin(2 * math.pi * j / seg2)) * minor) for j in range(seg2)])
    for i in range(seg):
        for j in range(seg2):
            a, b = rings[i], rings[(i + 1) % seg]
            bm.faces.new((a[j], b[j], b[(j + 1) % seg2], a[(j + 1) % seg2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot[2]), 3, "Z")
                     @ Matrix.Rotation(math.radians(rot[1]), 3, "Y") @ Matrix.Rotation(math.radians(rot[0]), 3, "X"))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material or mat("wire", (0.2, 0.2, 0.19)))
    o.location = loc
    if parent:
        o.parent = parent
    return o


def concertina(y0, y1, z, radius, parent=None, pitch=0.28, name="coil"):
    """A concertina coil of barbed/razor wire along y from y0 to y1, its axis at height z: rings leaning
    alternately, as the stretched coil reads."""
    out = []
    n = max(2, round((y1 - y0) / pitch))
    for i in range(n):
        y = y0 + (i + 0.5) * (y1 - y0) / n
        out.append(torus(name, radius, 0.01, (0, y, z), rot=(0, 0, 90 + (14 if i % 2 else -14)), seg=12, parent=parent))
    return out


def wall_piece(x0, x1, name="hull"):
    """A slice x0..x1 (source metres) of the concrete wall source, without its razor wire, turned to run
    along +y and standing on the ground, centred on x = 0 and starting at y = 0."""
    o = convert.load(WALL_SOURCE, name)
    convert.raw_colours(o)
    crop(o, (x0, None, None), (x1, None, 3.99))
    fit(o, rot=90)
    lo, hi = convert.bounds(o)
    o.data.transform(Matrix.Translation((0, -lo.y, 0)))
    return o


def root(o):
    """Makes a hand-built part the model's root: its placement baked into the mesh, its origin at the
    ground under the centre (parts parented to it are then placed in model coordinates)."""
    o.data.transform(Matrix.Translation(o.location))
    o.location = (0, 0, 0)
    return o


def gate(turn=0.0):
    """A closed gate filling a 3-cell gap (12 m of model at Scale 2) along x before turn (degrees): concrete
    pillars at both ends cut from the BRIK wall source, two 4.7 m steel leaves between them - a box frame,
    bars every 20 cm, a mid rail, a diagonal brace, closed, a razor coil above."""
    steel = mat("gate_steel", (0.25, 0.27, 0.22))
    pillars = []
    for side in (-1, 1):
        o = wall_piece(6.0, 7.28, "hull" if side < 0 else "pillar")
        lo, hi = convert.bounds(o)
        w = hi.y - lo.y
        o.data.transform(Matrix.Translation((side * (6.0 - w / 2), 0, 0)) @ Matrix.Rotation(math.radians(-90), 4, "Z")
                         @ Matrix.Translation((0, -(lo.y + hi.y) / 2, 0)))
        pillars.append(o)
    hull = pillars[0]
    inner = 6.0 - w
    for side in (-1, 1):
        cx, lw = side * inner / 2, inner - 0.05
        for z in (0.15, 1.5, 2.95):
            box("leaf_rail", (lw, 0.08, 0.1), (cx, 0, z), steel, parent=hull)
        for x in (cx - lw / 2, cx + lw / 2):
            box("leaf_stile", (0.1, 0.1, 2.9), (x, 0, 1.55), steel, parent=hull)
        for i in range(int(lw / 0.2)):
            box("leaf_bar", (0.03, 0.03, 2.8), (cx - lw / 2 + 0.15 + i * 0.2, 0, 1.55), steel, parent=hull)
        box("leaf_brace", (lw * 1.12, 0.06, 0.08), (cx, 0.05, 0.85), steel, parent=hull, rot=(0, 20 * side, 0))
    box("latch", (0.15, 0.2, 0.3), (0, 0, 1.5), mat("black", BLACK), parent=hull)
    n = int(2 * inner / 0.28)
    for i in range(n):
        torus("coil", 0.3, 0.01, (-inner + (i + 0.5) * 2 * inner / n, 0, 3.4), rot=(0, 0, (14 if i % 2 else -14)), seg=12)
    if turn:
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.parent is None]
        for o in objs:
            o.data.transform(Matrix.Translation(o.location))
            o.location = (0, 0, 0)
            o.data.transform(Matrix.Rotation(math.radians(turn), 4, "Z"))
        for o in [o for o in bpy.context.scene.objects if o.parent == hull]:
            o.location = Matrix.Rotation(math.radians(turn), 4, "Z") @ o.location
            o.rotation_euler.z += math.radians(turn)
    return done(hull)
