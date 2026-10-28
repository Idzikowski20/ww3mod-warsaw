"""Turning a downloaded .glb into a unit model (run inside Blender, from a units/<name>.py build()).

Typical build():

    o = convert.load("t90_source.glb")                       # one mesh, skins and empties gone
    convert.normalize(o, front="-Y", length=9.53)              # front to +Y, centred, on the ground, real size
    convert.decimate(o, 20000)
    parts = convert.split(o, {                                 # triangles by centroid, first rule wins
        "barrel": lambda c: abs(c.x) < 0.2 and c.y > 2.0 and c.z > 1.6,
        "turret": lambda c: c.z > 1.55 and (c.x ** 2 + (c.y - 0.4) ** 2) < 1.3 ** 2,
    }, rest="hull")
    convert.pivot(parts["turret"], (0, 0.4, 1.55))             # turns about the turret ring
    convert.pivot(parts["barrel"], (0, 1.6, 1.9))
    convert.parent(parts["barrel"], parts["turret"])
    convert.parent(parts["turret"], parts["hull"])

then lib.finish(..., flat=False) bakes, outlines and exports (build.py calls it).
Sources live in WORKSPACE/m4-refs/sources/.
"""

import math
import os
import bmesh
import bpy
from mathutils import Matrix, Vector

SOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "WORKSPACE", "m4-refs", "sources")


def load(filename, name="hull"):
    """Imports a source .glb and returns it as one mesh object in its posed shape (armatures applied and
    removed, transforms applied), named name. Materials and their textures are kept."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SOURCES, filename))
    new = [o for o in bpy.data.objects if o not in before]
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = []
    for o in new:
        if o.type != "MESH":
            continue
        # Freeze the evaluated shape (skinning, modifiers, shape keys) in world space.
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        flat = bpy.data.objects.new(o.name, me)
        bpy.context.scene.collection.objects.link(flat)
        meshes.append(flat)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        raise RuntimeError(f"{filename}: no meshes")
    _join(meshes)
    o = meshes[0]
    o.name = name
    o.data.name = name
    weld(o)
    return o


def weld(o, angle=40):
    """Merges coincident vertices. A glTF source splits them at every seam and hard edge, so each triangle is
    its own piece: the bake's UV unwrap then gives every triangle a sub-pixel island that bakes black, and
    decimation cannot collapse across pieces. Hard edges come back from the face angle."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(o.data)
    bm.free()
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.set_sharp_from_angle(angle=math.radians(angle))


def raw_colours(o):
    """Flat (untextured) base colours of a downloaded model, glTF-linear, turned into the display values the
    bake stores and the engine shows as they are. Marks each material, so calling it twice is harmless."""
    for m in o.data.materials:
        if m is None or not m.use_nodes or m.get("raw_colour"):
            continue
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and not n.inputs["Base Color"].is_linked:
                c = n.inputs["Base Color"].default_value
                n.inputs["Base Color"].default_value = (*(_srgb(v) for v in c[:3]), c[3])
        m["raw_colour"] = True


def _srgb(v):
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def _join(objs):
    if len(objs) < 2:
        return
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs,
                                   selected_objects=objs):
        bpy.ops.object.join()


def bounds(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def normalize(o, front="-Y", length=None, width=None, height=None, scale=None, centre=True):
    """Bakes into the mesh: the front turned to +Y (front is where the source's nose points: "+Y", "-Y",
    "+X", "-X"), scaled so its length along y (or width along x, or height) is that many metres, or by
    scale, centred on x/y and standing on z = 0."""
    # Counter-clockwise about +Z by turn: a nose at +X goes to +Y with +90.
    turn = {"+Y": 0, "-Y": 180, "+X": 90, "-X": -90}[front]
    m = Matrix.Rotation(math.radians(turn), 4, "Z") if turn else Matrix.Identity(4)
    o.data.transform(m)
    lo, hi = bounds(o)
    size = hi - lo
    k = scale or (length / size.y if length else width / size.x if width else height / size.z if height else 1.0)
    c = (lo + hi) / 2
    o.data.transform(Matrix.Translation((-c.x if centre else 0, -c.y if centre else 0, -lo.z)))
    o.data.transform(Matrix.Scale(k, 4))
    lo, hi = bounds(o)
    print(f"normalized {o.name}: x {lo.x:.2f}..{hi.x:.2f}  y {lo.y:.2f}..{hi.y:.2f}  z {lo.z:.2f}..{hi.z:.2f}")
    return lo, hi


def decimate(o, target_tris):
    """Collapse-decimates o to about target_tris triangles (UVs kept)."""
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if tris <= target_tris:
        return
    mod = o.modifiers.new("decimate", "DECIMATE")
    mod.ratio = target_tris / tris
    mod.use_collapse_triangulate = True
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"decimated {o.name}: {tris} -> {sum(len(p.vertices) - 2 for p in o.data.polygons)} tris")


def split(o, rules, rest=None):
    """Splits o's faces into new objects by rules {name: predicate(centroid Vector) -> bool}, tried in
    order, first match wins. Faces matching nothing stay in o (renamed rest, if given). Returns
    {name: object} including o under its (new) name. Centroids are in o's mesh space (after normalize)."""
    if rest:
        o.name = rest
    out = {o.name: o}
    names = list(rules)
    owner = []
    for p in o.data.polygons:
        c = p.center
        owner.append(next((i for i, n in enumerate(names) if rules[n](c)), -1))
    for i, n in enumerate(names):
        idx = {k for k, w in enumerate(owner) if w == i}
        if not idx:
            print(f"split {n}: no faces matched")
            continue
        me = o.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in idx], context="FACES")
        bm.to_mesh(me)
        bm.free()
        part = bpy.data.objects.new(n, me)
        bpy.context.scene.collection.objects.link(part)
        out[n] = part
        print(f"split {n}: {len(idx)} faces")
    keep = {k for k, w in enumerate(owner) if w == -1}
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    return out


def pivot(o, point):
    """Moves o's origin to point (world metres) without moving its geometry: the node turns about it."""
    point = Vector(point)
    delta = point - o.matrix_world.translation
    o.data.transform(Matrix.Translation(-delta))
    o.matrix_world.translation = point


def parent(child, parent_obj):
    """Parents child to parent_obj keeping its world placement."""
    mw = child.matrix_world.copy()
    child.parent = parent_obj
    child.matrix_world = mw


def recolor(o, rgb, amount=0.6):
    """Tints every textured material of o toward rgb by amount (0..1), keeping the texture's light and
    dark: for a faction colour on a borrowed model. Applied before the bake."""
    for m in o.data.materials:
        if m is None or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
            continue
        link = bsdf.inputs["Base Color"].links[0]
        src = link.from_socket
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(src, bw.inputs[0])
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs["Factor"].default_value = 1.0
        a = next(x for x in tint.inputs if x.name == "A" and x.type == "RGBA")
        b = next(x for x in tint.inputs if x.name == "B" and x.type == "RGBA")
        nt.links.new(bw.outputs[0], a)
        b.default_value = (rgb[0] * 2.2, rgb[1] * 2.2, rgb[2] * 2.2, 1)
        blend = nt.nodes.new("ShaderNodeMix")
        blend.data_type = "RGBA"
        blend.inputs["Factor"].default_value = amount
        a2 = next(x for x in blend.inputs if x.name == "A" and x.type == "RGBA")
        b2 = next(x for x in blend.inputs if x.name == "B" and x.type == "RGBA")
        nt.links.new(src, a2)
        nt.links.new(next(x for x in tint.outputs if x.type == "RGBA"), b2)
        nt.links.new(next(x for x in blend.outputs if x.type == "RGBA"), bsdf.inputs["Base Color"])


TEXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")


def track_belts(o, select, tile_image="track_tile.png", tile_length=0.7, depth=0.1):
    """Gives o's track belts the scrolling track texture (engine: material "track*", gltf.frag TrackScroll).
    The faces select(face_centre, face_normal) picks (mesh space, both belts) move into material "track" textured
    with tile_image (a file in tools/models/textures/, or a path), with UVs laid for the scroll: u across the belt,
    v the arc length round the belt's side profile in tiles. The profile is the outline (convex hull) of each
    belt's (y, z) face centres (centres: a big face reaching out of the belt does not bend it), so the top run,
    the bottom run and the wraps round sprocket and idler are one strip; picked faces deeper than depth inside
    it (road wheels) keep their material. The tile is stretched a little so
    a whole number fits round the belt (no seam). Returns that tile length, model metres."""
    from mathutils import geometry
    me = o.data
    m = bpy.data.materials.get("track")
    if m is None:
        m = bpy.data.materials.new("track")
        m.use_nodes = True
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(TEXTURES, tile_image), check_existing=True)
        tex.image.colorspace_settings.name = "Non-Color"  # display values, shown as they are
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if m.name not in me.materials:
        me.materials.append(m)
    slot = list(me.materials).index(m)
    if not me.uv_layers:
        me.uv_layers.new()
    uv = me.uv_layers[0].data  # lib.bake keeps this layer's UVs on track faces
    V = me.vertices
    chosen = [p for p in me.polygons if select(p.center, p.normal)]
    tile = tile_length
    for side in (1, -1):
        faces = [p for p in chosen if p.center.x * side > 0]
        if not faces:
            continue
        pts = [p.center for p in faces]
        # The belt's axis in plan (a source can sit a degree or two off +Y): the centres' principal axis.
        n = len(pts)
        mx, my = sum(v.x for v in pts) / n, sum(v.y for v in pts) / n
        cxx = sum((v.x - mx) ** 2 for v in pts)
        cyy = sum((v.y - my) ** 2 for v in pts)
        cxy = sum((v.x - mx) * (v.y - my) for v in pts)
        a = 0.5 * math.atan2(2 * cxy, cxx - cyy)
        ca, sa = (math.cos(a), math.sin(a)) if math.sin(a) >= 0 else (-math.cos(a), -math.sin(a))

        def frame(v):  # (along the belt, forward; across it, ~x; z)
            return v.x * ca + v.y * sa, v.x * sa - v.y * ca, v.z

        prof = [Vector((f[0], f[2])) for f in map(frame, pts)]
        hull = [prof[i] for i in geometry.convex_hull_2d(prof)]
        # Counter-clockwise seen from +x (forward to the right, z up): the top run runs front to back.
        if sum(h.x * k.y - k.x * h.y for h, k in zip(hull, hull[1:] + hull[:1])) < 0:
            hull.reverse()
        edges = list(zip(hull, hull[1:] + hull[:1]))
        cum = [0.0]
        for h, k in edges:
            cum.append(cum[-1] + (k - h).length)
        perimeter = cum[-1]
        tile = perimeter / max(1, round(perimeter / tile_length))

        def arc(f):  # (arc length of the outline point nearest f, distance to it)
            q = Vector((f[0], f[2]))
            best = (0.0, float("inf"))
            for i, (h, k) in enumerate(edges):
                e = k - h
                t = max(0.0, min(1.0, (q - h).dot(e) / e.length_squared)) if e.length_squared else 0.0
                d = (h + e * t - q).length
                if d < best[1]:
                    best = (cum[i] + t * e.length, d)
            return best

        faces = [p for p in faces if arc(frame(p.center))[1] <= depth]
        across = [frame(V[i].co)[1] for p in faces for i in p.vertices]
        a0, a1 = min(across), max(across)
        for p in faces:
            p.material_index = slot
            s0 = None
            for li in p.loop_indices:
                f = frame(V[me.loops[li].vertex_index].co)
                s = arc(f)[0]
                s0 = s if s0 is None else s0
                s -= perimeter * round((s - s0) / perimeter)  # a face across the outline's start stays whole
                # glTF stores 1 - v: -s here makes the engine's v run counter-clockwise, as TrackScroll expects.
                uv[li].uv = ((f[1] - a0) / (a1 - a0), -s / tile)
        print(f"track_belts {o.name} side {side:+d}: {len(faces)} faces, belt {perimeter:.2f} m round, "
              f"tile {tile:.3f} m, axis {math.degrees(math.atan2(ca, sa)):+.1f} deg off +Y")
    return tile
