"""Street surfaces and street props for the 3D Warsaw map, made in Blender 5.x (run in background).

Surfaces: seamless top-down textures of worn post-war city ground (asphalt, concrete pavement slabs,
granite setts, grass, kerb granite, red cycle asphalt, parking asphalt, bare soil, water), rendered
orthographically in Cycles. build_streets.py packs them into an atlas and tiles them in metres.

Props: low-poly but detailed models (Warsaw street lamp, traffic signal, three trees, four cars),
exported as flat-shaded triangles with a colour per material. A material whose name starts with
"Tint" is multiplied by the per-instance colour in the engine (car paint, tree crowns).

Usage: blender -b -P blender_streets.py -- <surfaces out dir> <props out json>
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

TILE_PX = 1024

# name: tile size in metres (the render covers size x size, top-down).
SURFACES = {
    "asphalt": 4.0, "slabs": 2.0, "setts": 2.0, "grass": 4.0, "kerb": 1.0,
    "cycle": 4.0, "parking": 4.0, "soil": 4.0, "water": 8.0,
}


def lin(c):
    return tuple(x ** 2.2 for x in c)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def enable_gpu(scene):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type != "CPU" for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type != "CPU"
            scene.cycles.device = "GPU"
            return


# --- Material helpers --------------------------------------------------------------------------------
class Nodes:
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.bsdf = next(n for n in self.nt.nodes if n.type == "BSDF_PRINCIPLED")
        self.coord = self.new("ShaderNodeTexCoord").outputs["Object"]

    def new(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def noise(self, scale, detail=4.0, roughness=0.5, vec=None):
        n = self.new("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=roughness)
        self.link(vec or self.coord, n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(self, fac, lo, hi):
        r = self.new("ShaderNodeMapRange", **{"From Min": lo, "From Max": hi})
        self.link(fac, r.inputs["Value"])
        return r.outputs["Result"]

    def rgb(self, c):
        n = self.new("ShaderNodeRGB")
        n.outputs[0].default_value = (*lin(c), 1.0)
        return n.outputs[0]

    def mix(self, a, b, fac):
        m = self.new("ShaderNodeMix")
        m.data_type = "RGBA"
        cols = [i for i in m.inputs if i.type == "RGBA"]
        self.link(fac, next(i for i in m.inputs if i.type == "VALUE"))
        self.link(a, cols[0])
        self.link(b, cols[1])
        return next(o for o in m.outputs if o.type == "RGBA")

    def scale(self, fac, k):
        m = self.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        m.inputs[1].default_value = k
        self.link(fac, m.inputs[0])
        return m.outputs[0]

    def finish(self, colour, roughness=0.9, bump=None, bump_strength=0.3):
        self.link(colour, self.bsdf.inputs["Base Color"])
        self.bsdf.inputs["Roughness"].default_value = roughness
        if bump is not None:
            b = self.new("ShaderNodeBump", Strength=bump_strength)
            self.link(bump, b.inputs["Height"])
            self.link(b.outputs["Normal"], self.bsdf.inputs["Normal"])


def grime(n, colour, amount, stains=0.4):
    """Common dirt: large blotches, fine grit, dark stains."""
    blotch = n.ramp(n.noise(0.6, 6), 0.3, 0.75)
    grit = n.noise(60, 2)
    stain = n.ramp(n.noise(1.5, 3), 0.62, 0.70)
    dark = n.rgb((0.10, 0.10, 0.09))
    c = n.mix(colour, dark, n.scale(blotch, 0.35 * amount))
    c = n.mix(c, dark, n.scale(grit, 0.25 * amount))
    return n.mix(c, dark, n.scale(stain, stains * amount))


def surface_material(name):
    mat = bpy.data.materials.new(name)
    n = Nodes(mat)
    if name == "asphalt" or name == "parking" or name == "cycle":
        base = {"asphalt": (0.24, 0.24, 0.25), "parking": (0.30, 0.30, 0.30), "cycle": (0.46, 0.22, 0.19)}[name]
        aggregate = n.noise(180, 1)
        c = n.mix(n.rgb(base), n.rgb(tuple(x * 1.5 for x in base)), n.scale(n.ramp(aggregate, 0.55, 0.75), 0.6))
        # Patched repairs: rectangles of darker, newer asphalt.
        patch = n.new("ShaderNodeTexVoronoi", Scale=0.7)
        patch.feature = "F1"
        n.link(n.coord, patch.inputs["Vector"])
        patch_mask = n.ramp(n.noise(0.8, 2), 0.66, 0.67)
        c = n.mix(c, n.rgb(tuple(x * 0.7 for x in base)), n.scale(patch_mask, 0.8))
        # Cracks: thin dark voronoi edges, gated to some areas.
        cracks = n.new("ShaderNodeTexVoronoi", Scale=3.0)
        cracks.feature = "DISTANCE_TO_EDGE"
        n.link(n.coord, cracks.inputs["Vector"])
        crack = n.ramp(cracks.outputs["Distance"], 0.03, 0.0)
        gate = n.ramp(n.noise(0.9, 2), 0.5, 0.6)
        m = n.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        n.link(crack, m.inputs[0])
        n.link(gate, m.inputs[1])
        c = n.mix(c, n.rgb((0.05, 0.05, 0.05)), m.outputs[0])
        n.finish(grime(n, c, 1.0, stains=0.6), 0.85, aggregate, 0.15)
    elif name == "slabs":
        # Communist-era 50 cm concrete pavement slabs: per-slab tone, broken corners, dark joints.
        brick = n.new("ShaderNodeTexBrick", Scale=1.0, **{"Mortar Size": 0.012, "Brick Width": 0.5,
                                                            "Row Height": 0.5, "Mortar Smooth": 0.2})
        brick.offset = 0.0
        n.link(n.coord, brick.inputs["Vector"])
        brick.inputs["Color1"].default_value = (*lin((0.56, 0.55, 0.52)), 1.0)
        brick.inputs["Color2"].default_value = (*lin((0.48, 0.47, 0.45)), 1.0)
        brick.inputs["Mortar"].default_value = (*lin((0.18, 0.17, 0.15)), 1.0)
        c = grime(n, brick.outputs["Color"], 1.0, stains=0.5)
        n.finish(c, 0.9, n.scale(brick.outputs["Fac"], -1.0), 0.4)
    elif name == "setts":
        brick = n.new("ShaderNodeTexBrick", Scale=1.0, **{"Mortar Size": 0.012, "Brick Width": 0.11,
                                                            "Row Height": 0.10, "Mortar Smooth": 0.5})
        n.link(n.coord, brick.inputs["Vector"])
        brick.inputs["Color1"].default_value = (*lin((0.46, 0.44, 0.42)), 1.0)
        brick.inputs["Color2"].default_value = (*lin((0.36, 0.35, 0.34)), 1.0)
        brick.inputs["Mortar"].default_value = (*lin((0.16, 0.15, 0.13)), 1.0)
        c = n.mix(brick.outputs["Color"], n.rgb((0.55, 0.50, 0.44)), n.scale(n.noise(25, 2), 0.3))
        n.finish(grime(n, c, 0.8), 0.8, n.scale(brick.outputs["Fac"], -1.0), 0.6)
    elif name == "grass":
        c = n.mix(n.rgb((0.20, 0.30, 0.12)), n.rgb((0.36, 0.40, 0.18)), n.noise(3, 6))
        worn = n.ramp(n.noise(0.5, 5), 0.55, 0.70)
        c = n.mix(c, n.rgb((0.36, 0.30, 0.22)), worn)
        c = n.mix(c, n.rgb((0.10, 0.16, 0.06)), n.scale(n.noise(90, 2), 0.5))
        n.finish(c, 0.95, n.noise(90, 2), 0.3)
    elif name == "kerb":
        c = n.mix(n.rgb((0.55, 0.54, 0.52)), n.rgb((0.40, 0.39, 0.38)), n.noise(40, 3))
        n.finish(grime(n, c, 1.2), 0.85, n.noise(40, 3), 0.2)
    elif name == "soil":
        c = n.mix(n.rgb((0.40, 0.33, 0.25)), n.rgb((0.30, 0.25, 0.19)), n.noise(4, 6))
        n.finish(c, 1.0, n.noise(30, 4), 0.5)
    elif name == "water":
        c = n.mix(n.rgb((0.16, 0.20, 0.20)), n.rgb((0.22, 0.27, 0.27)), n.noise(1.5, 3))
        n.finish(c, 0.15)
    return mat


def render_surface(name, out_dir):
    reset()
    scene = bpy.context.scene
    enable_gpu(scene)
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    size = SURFACES[name]
    bpy.ops.mesh.primitive_plane_add(size=size * 3, location=(size / 2, size / 2, 0))
    plane = bpy.context.active_object
    plane.data.materials.append(surface_material(name))
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    bg = next(nd for nd in world.node_tree.nodes if nd.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.8, 0.82, 0.85, 1)
    bg.inputs[1].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 1.5
    sun.rotation_euler = (math.radians(35), 0, math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = size
    cam.location = (size / 2, size / 2, 10)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x = scene.render.resolution_y = TILE_PX
    scene.render.filepath = os.path.join(out_dir, f"surface_{name}.png")
    bpy.ops.render.render(write_still=True)


# --- Props ---------------------------------------------------------------------------------------
def material(name, colour, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat["colour"] = list(colour)
    return mat


def add(bm, geom_fn, mat_index, matrix=Matrix()):
    """Runs a bmesh primitive into `bm` and tags its faces with a material."""
    before = set(bm.faces)
    geom_fn(bm)
    new = [f for f in bm.faces if f not in before]
    bmesh.ops.transform(bm, matrix=matrix, verts=list({v for f in new for v in f.verts}))
    for f in new:
        f.material_index = mat_index
    return new


def cylinder(bm, r1, r2, h, segs, mat, at=(0, 0, 0), rot=None):
    m = Matrix.Translation(Vector(at) + Vector((0, 0, h / 2)))
    if rot is not None:
        m = Matrix.Translation(at) @ rot @ Matrix.Translation((0, 0, h / 2))
    add(bm, lambda b: bmesh.ops.create_cone(b, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h), mat, m)


def cube(bm, size, at, mat):
    add(bm, lambda b: bmesh.ops.create_cube(b, size=1.0), mat,
        Matrix.Translation(at) @ Matrix.Diagonal((*size, 1.0)))


def blob(bm, r, at, mat, rnd, squash=0.8):
    m = Matrix.Translation(at) @ Matrix.Diagonal((r * rnd.uniform(0.85, 1.15), r * rnd.uniform(0.85, 1.15), r * squash, 1.0))
    faces = add(bm, lambda b: bmesh.ops.create_icosphere(b, subdivisions=1, radius=1.0), mat, m)
    for v in {v for f in faces for v in f.verts}:
        v.co += (v.co - Vector(at)).normalized() * r * rnd.uniform(-0.12, 0.12)


def lamp(bm, mats):
    # Warsaw street lamp: tapered grey steel pole, curved outreach arm, flat LED/sodium luminaire.
    cylinder(bm, 0.11, 0.07, 9.0, 10, mats["steel"])
    cylinder(bm, 0.16, 0.14, 0.9, 10, mats["steel"])
    for k in range(6):
        a = k / 6
        x0, z0 = 1.6 * a, 9.0 + 0.5 * math.sin(a * math.pi * 0.9)
        cube(bm, (0.30, 0.08, 0.08), (x0 + 0.15, 0, z0), mats["steel"])
    cube(bm, (0.75, 0.28, 0.12), (1.8, 0, 9.35), mats["lampbody"])
    cube(bm, (0.6, 0.22, 0.03), (1.8, 0, 9.28), mats["lens"])


def signal(bm, mats):
    cylinder(bm, 0.07, 0.06, 3.6, 8, mats["steel"])
    cube(bm, (0.32, 0.26, 0.95), (0, 0.18, 3.0), mats["signalbody"])
    for k, c in enumerate(("red", "amber", "green")):
        cube(bm, (0.18, 0.04, 0.18), (0, 0.33, 3.3 - k * 0.3), mats[c])
    cube(bm, (0.30, 0.20, 0.45), (0, -0.16, 1.2), mats["signalbody"])


def tree(bm, mats, seed, kind):
    rnd = random.Random(seed)
    if kind == "conifer":
        cylinder(bm, 0.22, 0.12, 3.0, 7, mats["bark"])
        for k in range(4):
            cylinder(bm, 2.6 - k * 0.55, 0.1, 3.4, 9, mats["TintLeaves"], at=(0, 0, 2.0 + k * 2.0))
        return
    h = 3.5 if kind == "lime" else 2.6
    cylinder(bm, 0.28, 0.18, h + 1.5, 7, mats["bark"])
    crown = 4.2 if kind == "lime" else 3.4
    centre = Vector((0, 0, h + crown * 0.9))
    blob(bm, crown, centre, mats["TintLeaves"], rnd, 0.9)
    for k in range(4):
        a = k * math.pi / 2 + rnd.uniform(-0.4, 0.4)
        off = Vector((math.cos(a) * crown * 0.55, math.sin(a) * crown * 0.55, rnd.uniform(-1.0, 1.2)))
        blob(bm, crown * rnd.uniform(0.55, 0.7), centre + off, mats["TintLeavesDark"] if k % 2 else mats["TintLeaves"], rnd)


def car(bm, mats, kind):
    # Proportions in metres: length, width, body height, cabin length/height/offset, roof bias.
    spec = {
        "sedan": (4.6, 1.8, 0.75, 2.5, 0.55, -0.1),
        "hatch": (4.1, 1.75, 0.75, 2.3, 0.60, -0.35),
        "van": (5.0, 1.95, 1.05, 3.6, 0.95, -0.55),
        "small": (3.3, 1.55, 0.70, 1.9, 0.55, -0.25),
    }[kind]
    length, width, body, cab, cab_h, cab_off = spec
    clearance = 0.18
    cube(bm, (length, width, body), (0, 0, clearance + body / 2), mats["TintPaint"])
    cube(bm, (cab, width * 0.86, cab_h), (cab_off, 0, clearance + body + cab_h / 2), mats["glass"])
    cube(bm, (cab - 0.25, width * 0.82, 0.05), (cab_off, 0, clearance + body + cab_h + 0.02), mats["TintPaint"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            cylinder(bm, 0.32, 0.32, 0.22, 10, mats["tyre"], at=(sx * length * 0.32, sy * (width / 2 - 0.08) - 0.11, 0.32),
                     rot=Matrix.Rotation(math.pi / 2, 4, "X"))
    cube(bm, (0.05, width * 0.8, 0.12), (length / 2, 0, clearance + body * 0.6), mats["lights"])
    cube(bm, (0.05, width * 0.8, 0.12), (-length / 2, 0, clearance + body * 0.6), mats["rearlights"])


PROPS = {
    "lamp": lambda bm, m: lamp(bm, m),
    "signal": lambda bm, m: signal(bm, m),
    "tree_lime": lambda bm, m: tree(bm, m, 1, "lime"),
    "tree_maple": lambda bm, m: tree(bm, m, 2, "maple"),
    "tree_conifer": lambda bm, m: tree(bm, m, 3, "conifer"),
    "car_sedan": lambda bm, m: car(bm, m, "sedan"),
    "car_hatch": lambda bm, m: car(bm, m, "hatch"),
    "car_van": lambda bm, m: car(bm, m, "van"),
    "car_small": lambda bm, m: car(bm, m, "small"),
}

COLOURS = {
    "steel": (0.34, 0.35, 0.35), "lampbody": (0.22, 0.22, 0.23), "lens": (0.75, 0.70, 0.55),
    "signalbody": (0.10, 0.10, 0.10), "red": (0.55, 0.08, 0.06), "amber": (0.55, 0.40, 0.08), "green": (0.10, 0.45, 0.25),
    "bark": (0.28, 0.23, 0.18), "TintLeaves": (1.0, 1.0, 1.0), "TintLeavesDark": (0.78, 0.80, 0.76),
    "TintPaint": (1.0, 1.0, 1.0), "glass": (0.09, 0.11, 0.13), "tyre": (0.06, 0.06, 0.06),
    "lights": (0.80, 0.78, 0.70), "rearlights": (0.45, 0.06, 0.05),
}


def export_props(path):
    """Writes {name: [[x, y, z, nx, ny, nz, r, g, b, tint], ...]} in metres, engine axes (x, up, -y)."""
    out = {}
    names = list(COLOURS)
    for prop, build in PROPS.items():
        bm = bmesh.new()
        build(bm, {n: i for i, n in enumerate(names)})
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        tris = []
        for f in bm.faces:
            mname = names[f.material_index]
            r, g, b = COLOURS[mname]
            tint = 1.0 if mname.startswith("Tint") else 0.0
            nx, ny, nz = f.normal
            for v in f.verts:
                x, y, z = v.co
                tris.append([round(x, 3), round(z, 3), round(-y, 3), round(nx, 3), round(nz, 3), round(-ny, 3), r, g, b, tint])
        bm.free()
        out[prop] = tris
        print("prop", prop, len(tris) // 3, "triangles", flush=True)
    with open(path, "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    surf_dir, props_path = args[0], args[1]
    os.makedirs(surf_dir, exist_ok=True)
    export_props(props_path)
    for name in SURFACES:
        render_surface(name, surf_dir)
        print("rendered", name, flush=True)
