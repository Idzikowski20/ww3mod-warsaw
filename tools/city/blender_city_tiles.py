"""Builds the tiles of the generated city map in background Blender and exports them for build_city_map.py.

Two sources, both supplied by the user (kept outside the repository, see README in this folder):
  - an iCity export (glTF): European perimeter blocks with streets, sidewalks and parking, plus one tower.
  - "abandoned city.blend": a Geometry Nodes generator of ruined high-rises, used for the outer districts.
Layout follows Curtis Holt's City Scatter idea (big buildings in the centre, smaller and older outwards).

Each exported model is <name>.npz plus <name>.json (materials: base colour, image file, alpha, bounds in
metres) and the images it uses, saved as PNG next to them. The npz holds each distinct mesh once as
unindexed triangles in its local space (engine axes x east, y up, z south): float32 pos/nrm/uv, int32
material per vertex, mesh_first/mesh_count vertex ranges; and its instances: inst_mesh, inst_mat (n, 3, 4)
taking a mesh to engine metres around the model origin.

Usage:
  blender -b -P blender_city_tiles.py -- icity <icity City_Exports dir> <out dir>
  blender -b "<abandoned city.blend>" -P blender_city_tiles.py -- abandoned <out dir> <seed> <width> [<abandon 0..1>]
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

UNIT_ABANDONED = 3.0          # metres per generator unit (one storey)


def log(*a):
    print(*a, flush=True)


def tris_of(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH")


# --- Material reading ----------------------------------------------------------------------------------
def upstream_image(socket, depth=0):
    """First Image Texture feeding `socket`, walking back through mixes, maths and colour nodes."""
    if depth > 8 or not socket.is_linked:
        return None, None
    node = socket.links[0].from_node
    if node.type == "TEX_IMAGE" and node.image is not None:
        mapping = None
        vec = node.inputs.get("Vector")
        if vec is not None and vec.is_linked and vec.links[0].from_node.type == "MAPPING":
            mapping = vec.links[0].from_node
        return node.image, mapping
    for inp in node.inputs:
        if inp.type in ("RGBA", "VALUE", "SHADER") and inp.is_linked:
            img, mapping = upstream_image(inp, depth + 1)
            if img is not None:
                return img, mapping
    return None, None


def material_info(mat, out_dir, saved, prefix):
    """Base colour (sRGB), an image file name or None, the UV mapping to apply, and whether it is cut-out."""
    info = {"name": mat.name if mat else "none", "color": [0.6, 0.6, 0.6], "image": None, "alpha": False,
            "uv": None}
    if mat is None or not mat.use_nodes:
        if mat is not None:
            info["color"] = [c ** (1 / 2.2) for c in mat.diffuse_color[:3]]
        return info
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return info
    base = bsdf.inputs["Base Color"]
    info["color"] = [max(0.0, c) ** (1 / 2.2) for c in base.default_value[:3]]
    img, mapping = upstream_image(base)
    if bsdf.inputs.get("Transmission Weight") is not None and bsdf.inputs["Transmission Weight"].default_value > 0.5:
        info["color"] = [0.10, 0.13, 0.15]       # glass reads as dark from outside
        img = None
    if img is not None:
        key = img.name
        if key not in saved:
            fname = "%s_img_%04d.png" % (prefix, len(saved))
            try:
                img.scale(min(img.size[0], 1024), min(img.size[1], 1024)) if max(img.size) > 1024 else None
                img.save_render(os.path.join(out_dir, fname))
                saved[key] = fname
            except Exception as ex:  # an image Blender cannot read (missing file): fall back to the colour
                log("  image failed", img.name, ex)
                saved[key] = None
        info["image"] = saved[key]
        alpha = bsdf.inputs["Alpha"]
        info["alpha"] = bool(alpha.is_linked) or mat.blend_method in ("CLIP", "HASHED", "BLEND")
        if mapping is not None:
            info["uv"] = {"loc": list(mapping.inputs["Location"].default_value[:2]),
                          "rot": mapping.inputs["Rotation"].default_value[2],
                          "scale": list(mapping.inputs["Scale"].default_value[:2])}
    return info


# --- Export -----------------------------------------------------------------------------------------
def mesh_arrays(ev):
    """Triangle data of an evaluated object's mesh in its local space, or None when it has no faces."""
    me = ev.to_mesh()
    if len(me.polygons) > 25000:
        # The generator's subdivided ground: planar-dissolve it (bmesh, no depsgraph update while the
        # caller iterates instances), keeping UV islands and materials.
        bm = bmesh.new()
        bm.from_mesh(me)
        n = len(bm.faces)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts, edges=bm.edges,
                                 delimit={"UV", "MATERIAL"})
        log(f"  dissolved {ev.original.name}: {n:,} -> {len(bm.faces):,} faces")
        bm.to_mesh(me)
        bm.free()
    me.calc_loop_triangles()
    n_tri = len(me.loop_triangles)
    if n_tri == 0:
        ev.to_mesh_clear()
        return None
    loops = np.empty(n_tri * 3, np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    tri_mat = np.empty(n_tri, np.int64)
    me.loop_triangles.foreach_get("material_index", tri_mat)
    verts = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", verts)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    nrm = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    uv = np.zeros((len(me.loops), 2), np.float32)
    if me.uv_layers.active is not None:
        me.uv_layers.active.data.foreach_get("uv", uv.reshape(-1))
    slots = [s.material for s in ev.material_slots] or [None]
    ev.to_mesh_clear()
    return loops, tri_mat, co.reshape(-1, 3)[verts], nrm.reshape(-1, 3), uv, slots


# Blender (x, y, z up) -> engine (x east, y up, z south = -y).
TO_ENGINE = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], np.float32)


def export(pairs, name, out_dir, scale=1.0, origin=(0.0, 0.0)):
    """Writes (evaluated object, world matrix) pairs as one model <name>.npz / <name>.json: each distinct mesh
    once (unindexed triangles, its local space in engine axes) plus one 3x4 matrix per instance taking it to
    engine metres around `origin` (Blender x, y). The generator's instances stay instances."""
    os.makedirs(out_dir, exist_ok=True)
    saved = {}
    mats, mat_index = [], {}
    pos_l, nrm_l, uv_l, mid_l, first, count = [], [], [], [], [], []
    mesh_of = {}
    inst_mesh, inst_mat = [], []
    base = 0
    for ev, matrix in pairs:
        key = (ev.original.name, ev.data.name if ev.data else "")
        if key not in mesh_of:
            data = mesh_arrays(ev)
            if data is None:
                mesh_of[key] = None
                continue
            loops, tri_mat, local_co, nrm, uv, slots = data
            uv = uv.copy()
            local = []
            for mat in slots:
                mkey = mat.name if mat else "none"
                if mkey not in mat_index:
                    mat_index[mkey] = len(mats)
                    mats.append(material_info(mat, out_dir, saved, name))
                local.append(mat_index[mkey])
            local = np.array(local or [0], np.int64)
            loop_mat = np.zeros(len(uv), np.int64)
            loop_mat[loops] = local[np.minimum(np.repeat(tri_mat, 3), len(local) - 1)]
            # glTF texture transforms (Mapping nodes) baked into the UVs per material.
            for k in np.unique(loop_mat):
                t = mats[k]["uv"]
                if t is None:
                    continue
                sel = loop_mat == k
                c, s_ = math.cos(t["rot"]), math.sin(t["rot"])
                u, v = uv[sel, 0] * t["scale"][0], uv[sel, 1] * t["scale"][1]
                uv[sel, 0] = c * u - s_ * v + t["loc"][0]
                uv[sel, 1] = s_ * u + c * v + t["loc"][1]
            pos_l.append(local_co[loops] @ TO_ENGINE.T)
            nrm_l.append(nrm[loops] @ TO_ENGINE.T)
            uv_l.append(uv[loops])
            mid_l.append(loop_mat[loops])
            first.append(base)
            count.append(len(loops))
            base += len(loops)
            mesh_of[key] = len(first) - 1
        if mesh_of[key] is None:
            continue
        m = np.array(matrix, np.float32)
        lin = scale * (TO_ENGINE @ m[:3, :3] @ TO_ENGINE.T)
        t = TO_ENGINE @ (scale * m[:3, 3] - np.array([origin[0], origin[1], 0.0], np.float32))
        inst_mesh.append(mesh_of[key])
        inst_mat.append(np.hstack([lin, t[:, None]]))

    pos = np.concatenate(pos_l).astype(np.float32)
    inst_mesh = np.array(inst_mesh, np.int32)
    inst_mat = np.array(inst_mat, np.float32)
    first, count = np.array(first, np.int64), np.array(count, np.int64)
    # Bounds: every instance's mesh box corners, transformed.
    lo_m = np.array([pos[f:f + c].min(axis=0) for f, c in zip(first, count)])
    hi_m = np.array([pos[f:f + c].max(axis=0) for f, c in zip(first, count)])
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for k in range(8):
        corner = np.where([(k >> i) & 1 for i in range(3)], hi_m, lo_m)[inst_mesh]
        w = np.einsum("nij,nj->ni", inst_mat[:, :, :3], corner) + inst_mat[:, :, 3]
        lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
    np.savez_compressed(os.path.join(out_dir, name + ".npz"), pos=pos, nrm=np.concatenate(nrm_l).astype(np.float32),
                        uv=np.concatenate(uv_l).astype(np.float32), mat=np.concatenate(mid_l).astype(np.int32),
                        mesh_first=first, mesh_count=count, inst_mesh=inst_mesh, inst_mat=inst_mat)
    with open(os.path.join(out_dir, name + ".json"), "w") as f:
        json.dump({"materials": mats, "min": lo.tolist(), "max": hi.tolist()}, f, indent=1)
    drawn = int(count[inst_mesh].sum()) // 3
    log(f"exported {name}: {len(first)} meshes, {len(pos):,} vertices, {len(inst_mesh):,} instances, "
        f"{drawn:,} triangles drawn, {len(mats)} materials, bounds {np.round(lo, 1).tolist()} .. {np.round(hi, 1).tolist()}")


def set_input(mod, name, value):
    item = next(i for i in mod.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT" and i.name == name)
    getattr(mod.properties.inputs, item.identifier).value = value


def realise(obj):
    """Applies the object's modifiers and realises its instances into plain mesh objects."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return [o for o in bpy.context.selected_objects if o.type == "MESH"]


def decimate_heavy(objects, limit=1000, keep=0.15, floor=300):
    """Collapse-decimates every mesh above `limit` triangles to `keep` of its size (never below `floor`),
    replacing the mesh datablock for all its users, so every instance of it gets lighter."""
    done = set()
    for o in objects:
        if o.type != "MESH" or o.data.name in done:
            continue
        n = sum(len(p.vertices) - 2 for p in o.data.polygons)
        done.add(o.data.name)
        if n <= limit:
            continue
        d = o.modifiers.new("BudgetDecimate", "DECIMATE")
        d.ratio = max(keep, floor / n)
        bpy.context.view_layer.update()
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        light = bpy.data.meshes.new_from_object(ev)
        o.modifiers.remove(d)
        old = o.data
        old.user_remap(light)
        log(f"  decimated {o.name}: {n:,} -> {sum(len(p.vertices) - 2 for p in light.polygons):,} triangles")


BOX_COLLECTIONS = ("Walls", "Corner", "Ground Floor Wall", "Ground Floor Corner", "Top Floor Wall",
                   "Top Floor Convex Corner")


def gpu_cycles(scene, samples=8):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                break
        except TypeError:
            continue
    scene.cycles.samples = samples


def box_mesh(src, cells=(3, 2), inset=0.004):
    """The bounding box of `src` (local space) as a 12-triangle mesh, each face in its own UV cell."""
    co = np.empty(len(src.vertices) * 3, np.float32)
    src.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = [lo[i] if v.co[i] < 0 else hi[i] for i in range(3)]
    uv = bm.loops.layers.uv.new("UVMap")
    for f_i, f in enumerate(bm.faces):
        cx, cy = f_i % cells[0], f_i // cells[0]
        n = f.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != axis]
        for loop in f.loops:
            u = (loop.vert.co[a] - lo[a]) / max(hi[a] - lo[a], 1e-6)
            v = (loop.vert.co[b] - lo[b]) / max(hi[b] - lo[b], 1e-6)
            loop[uv].uv = ((cx + inset + u * (1 - 2 * inset)) / cells[0], (cy + inset + v * (1 - 2 * inset)) / cells[1])
    me = bpy.data.meshes.new(src.name + "_box")
    bm.to_mesh(me)
    bm.free()
    return me, float(max(hi - lo))


def bake_boxes(objects, size=512, limit=24):
    """Replaces every detailed modular wall piece (more than `limit` triangles) by its bounding box with the
    piece's look (Cycles diffuse colour) baked onto it: windows keep their frames as texture at a tenth of
    the triangles. Rays that miss the piece (open window holes) keep the dark interior colour."""
    bake = bpy.data.scenes.new("BoxBake")
    gpu_cycles(bake)
    bake.render.bake.use_selected_to_active = True
    bake.render.bake.use_pass_direct = False
    bake.render.bake.use_pass_indirect = False
    bake.render.bake.margin = 2
    done = set()
    for o in objects:
        if o.type != "MESH" or o.data.name in done:
            continue
        done.add(o.data.name)
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        if tris <= limit:
            continue
        me, extent = box_mesh(o.data)
        img = bpy.data.images.new(o.data.name + "_baked", size, size)
        img.generated_color = (0.035, 0.033, 0.03, 1.0)
        mat = bpy.data.materials.new(o.data.name + "_baked")
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.node_tree.nodes.active = tex
        me.materials.append(mat)
        high = bpy.data.objects.new("bake_high", o.data)
        low = bpy.data.objects.new("bake_low", me)
        for x in (high, low):
            bake.collection.objects.link(x)
        layer = bake.view_layers[0]
        for x in bake.objects:
            x.select_set(x in (high, low), view_layer=layer)
        with bpy.context.temp_override(scene=bake, view_layer=layer, active_object=low, object=low,
                                       selected_objects=[high, low], selected_editable_objects=[high, low]):
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True,
                                cage_extrusion=0.01 * extent, max_ray_distance=extent, margin=2)
        img.pack()
        bake.collection.objects.unlink(high)
        bake.collection.objects.unlink(low)
        bpy.data.objects.remove(high)
        bpy.data.objects.remove(low)
        o.data.user_remap(me)
        log(f"  baked {o.name}: {tris} -> 12 triangles")
    bpy.data.scenes.remove(bake)


# --- Sources ------------------------------------------------------------------------------------------
def abandoned(out_dir, seed, width, abandon):
    """`width` is the tile side in generator units: the plane is resized to it (the X/Y Width inputs are unused)."""
    city = bpy.data.objects["city"]
    sources = [o for c in bpy.data.collections if c.name in ("Building Modular Pieces", "Plants", "Other Objects")
               for o in c.all_objects]
    bake_boxes([o for c in bpy.data.collections if c.name in BOX_COLLECTIONS for o in c.objects])
    decimate_heavy(sources, limit=150, keep=0.15, floor=40)
    k = width / max(city.dimensions.x, 1e-6)
    for v in city.data.vertices:
        v.co.x *= k
        v.co.y *= k
    city.data.update()
    gen, plants, other = (city.modifiers[n] for n in ("City generation", "Plant generation", "Generation of other objects"))
    set_input(gen, "X Width", width)
    set_input(gen, "Y Width", width)
    set_input(gen, "X Roads", max(1, width // 20))
    set_input(gen, "Y Roads", max(1, width // 20))
    set_input(gen, "Building Seed", float(seed))
    set_input(gen, "Building Height Seed", seed % 1000)
    set_input(gen, "Abandoned Factor", abandon)
    # Budget: fewer trees and props than the showcase scene, one storey = 3 m.
    set_input(plants, "Tree Density Floor", 0.10)
    set_input(plants, "Tree Density Roof", 0.20)
    set_input(plants, "Grass Density", 0.12)
    set_input(other, "Rooftop Object Density", 0.3)
    set_input(other, "Standing Add Density", 0.4)
    city.location = (0, 0, 0)
    # The generator's buildings, plants and props are instances of the module objects: take each one
    # with its own world matrix, plus whatever geometry the city object realises itself (roads, ground).
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev_city = city.evaluated_get(dg)
    lo, hi = ev_city.bound_box[0], ev_city.bound_box[6]
    centre = ((lo[0] + hi[0]) / 2 * UNIT_ABANDONED, (lo[1] + hi[1]) / 2 * UNIT_ABANDONED)
    # Instance objects only live while the iterator is on them, so export consumes them as it goes.
    pairs = ((inst.object, inst.matrix_world.copy()) for inst in dg.object_instances
             if inst.object.type == "MESH" and (inst.is_instance or inst.object.original == city))
    if os.environ.get("CITY_PROBE"):
        budget(pairs)
        return
    export(pairs, f"abandoned_{seed}", out_dir, scale=UNIT_ABANDONED, origin=centre)


def budget(pairs):
    """Prints the triangle count per instanced mesh instead of exporting (CITY_PROBE=1)."""
    count, tri, owner = {}, {}, {}
    for ev, _ in pairs:
        name = ev.data.name
        count[name] = count.get(name, 0) + 1
        if name not in tri:
            tri[name] = sum(len(p.vertices) - 2 for p in ev.data.polygons)
            owner[name] = f"{ev.original.name} {tuple(round(d, 1) for d in ev.dimensions)}"
    rows = sorted(((count[n] * tri[n], n) for n in count), reverse=True)
    total = sum(r[0] for r in rows)
    log(f"budget total {total:,} triangles, {sum(count.values()):,} instances")
    for t, n in rows[:25]:
        log(f"  {n[:24]:24} x{count[n]:>6} * {tri[n]:>6} = {t:>11,}  {owner[n]}")


ICITY_DROP = ("Grass", "Path and Imperfections", "Parking Trees (High Poly)", "Grid Trees (High Poly)",
              "Sidewalk Trees (High Poly)", "Roundabout Trees (High Poly)", "Middle Island Trees (High Poly)")


def icity(src, out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = {"block": [("Building_unpacked_joined_GLTF", "Grid System.gltf"), ("Road_unpacked_joined_GLTF", "Road.gltf"),
                        ("Sidewalk_unpacked_joined_GLTF", "Sidewalk.gltf"), ("Parking_unpacked_joined_GLTF", "Parking.gltf")],
              "tower": [("Towers_unpacked_joined_GLTF", "Towers.gltf")]}
    for name, files in groups.items():
        before = set(bpy.data.objects)
        for sub, fname in files:
            bpy.ops.import_scene.gltf(filepath=os.path.join(src, sub, fname))
        objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        keep = []
        for o in objs:
            if any(o.name.startswith(d) for d in ICITY_DROP):
                bpy.data.objects.remove(o)
            else:
                keep.append(o)
        # The traffic-light export is ~670k triangles of fine detail and the parked cars ~650k: decimate.
        for o in keep:
            ratio = 0.08 if o.name.startswith("Traffic Lights") else 0.2 if o.name.startswith("Parking Block Cars") else None
            if ratio:
                d = o.modifiers.new("Decimate", "DECIMATE")
                d.ratio = ratio
        log(f"icity {name}: {len(keep)} objects, {tris_of(keep):,} triangles before decimation")
        dg = bpy.context.evaluated_depsgraph_get()
        export([(o.evaluated_get(dg), o.matrix_world.copy()) for o in keep], f"icity_{name}", out_dir)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    if args[0] == "icity":
        icity(args[1], args[2])
    else:
        abandoned(args[1], int(args[2]), int(args[3]), float(args[4]) if len(args) > 4 else 1.0)
