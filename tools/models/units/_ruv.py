"""Shared helpers for the Russian vehicles (btr, bmp2, giatsint, grad, tos, tunguska, iskander) and the
neutral support vehicles (TRUK, MSAR, LCCV, MNLY). Run inside Blender from a unit module's build().

Works around two gaps in convert.py (not edited, other domains share it):
- convert.normalize turns a +X / -X nose the wrong way (a +X nose ends up at -Y), so load() turns the
  mesh itself and normalizes with front="+Y";
- convert.split's rules see only the face centroid; split() here also passes the face's material name,
  which is how the sources that ship the turret as its own material are cut cleanly.
And one in lib.finish: it reads helper parts' matrix_world without a depsgraph update, so build() ends
with done(), which refreshes them (otherwise the first marking merged lands at the origin).
"""

import math
import bmesh
import bpy
from mathutils import Matrix

import convert

TURN = {"+Y": 0, "-Y": 180, "+X": 90, "-X": -90}
RU_GREEN = (0.22, 0.26, 0.15)    # Russian army green, for convert.recolor on sources in other paint


def load(filename, nose, length, tris=None, name="hull", shift_x=0.0):
    """Source .glb as one mesh: nose turned to +Y, centred, on the ground, length metres long, decimated
    to about tris triangles. shift_x moves it sideways after centring (a lopsided mirror or antenna puts the
    bounding-box centre off the vehicle's centre line)."""
    o = convert.load(filename, name)
    raw_textures(o)
    if TURN[nose]:
        o.data.transform(Matrix.Rotation(math.radians(TURN[nose]), 4, "Z"))
    convert.normalize(o, front="+Y", length=length)
    if shift_x:
        o.data.transform(Matrix.Translation((shift_x, 0, 0)))
    if tris:
        convert.decimate(o, tris)
    return o


def raw_textures(o):
    """Reads o's colour textures as raw values. lib.bake samples them as sRGB, i.e. converted to linear
    (a 0.3 texel becomes 0.07), then stores the result as raw values the engine shows as they are: a
    downloaded model came out about 4x too dark, near black. Non-Color keeps the texel as authored."""
    for m in o.data.materials:
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    n.image.colorspace_settings.name = "Non-Color"
                # The same for a flat colour: a glTF base colour factor is linear, the bake keeps it raw.
                if n.type == "BSDF_PRINCIPLED" and not n.inputs["Base Color"].is_linked:
                    c = n.inputs["Base Color"].default_value
                    n.inputs["Base Color"].default_value = (*(_srgb(v) for v in c[:3]), c[3])


def _srgb(v):
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def split(o, rules, rest="hull", verts=False):
    """Like convert.split, but each rule is pred(centroid, material_name), or with verts=True
    pred(centroid, material_name, vertex_coords). First match wins; unmatched faces stay in o (renamed rest).
    Returns {name: object}."""
    o.name = rest
    out = {rest: o}
    names = list(rules)
    mats = [m.name if m else "" for m in o.data.materials]
    owner = []
    for p in o.data.polygons:
        mname = mats[p.material_index] if p.material_index < len(mats) else ""
        args = (p.center, mname, [o.data.vertices[v].co for v in p.vertices]) if verts else (p.center, mname)
        owner.append(next((i for i, n in enumerate(names) if rules[n](*args)), -1))
    for i, n in enumerate(names):
        idx = {k for k, w in enumerate(owner) if w == i}
        if not idx:
            print(f"split {n}: no faces matched")
            continue
        part = bpy.data.objects.new(n, _subset(o.data, idx))
        bpy.context.scene.collection.objects.link(part)
        out[n] = part
        print(f"split {n}: {len(idx)} faces")
    keep = {k for k, w in enumerate(owner) if w == -1}
    me = _subset(o.data, keep)
    old = o.data
    o.data = me
    bpy.data.meshes.remove(old)
    o.data.name = rest
    return out


def _subset(me, faces):
    me = me.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in faces], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return me


def drop(o, pred):
    """Deletes o's faces whose centroid matches pred (a burnt-away tarp, a part rebuilt by hand)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pred(f.calc_center_median())], context="FACES")
    bm.to_mesh(o.data)
    bm.free()


def hit(o, origin, direction):
    """First point where a ray hits o's mesh (o's own space), or None: for seating markings on a surface."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    loc = bvh.ray_cast(origin, direction)[0]
    return loc


def top(o, x, y, start=20.0):
    """Height of o's upper surface at x, y."""
    p = hit(o, (x, y, start), (0, 0, -1))
    return p.z if p else 0.0










def tilt(o, roll=0.0, pitch=0.0, sink=0.0):
    """Wreck pose: o (the hull, origin on the ground) leaning on a burst tyre / broken track."""
    o.rotation_euler = (pitch, roll, 0)
    o.location.z -= sink


def turret_off(turret, barrel=None, lift=0.2, rot=(0.1, -0.15, 0.6), droop=-0.2):
    """Wreck pose: turret blown up off its ring and skewed, gun drooping."""
    turret.location.z += lift
    turret.rotation_euler = rot
    if barrel is not None:
        barrel.rotation_euler = (droop, 0, 0)


def done(root, keep=("hull", "turret", "barrel")):
    """End of build(). Works around two things in lib.finish, which merges every helper part into its nearest
    kept ancestor reading matrix_world as it goes:
    - nothing has updated the depsgraph, so matrix_world is stale (the first part merged lands at the origin);
    - a part parented to another helper part loses its place once that parent has been merged away.
    So: refresh the matrices, then hang every helper part directly on its nearest kept ancestor."""
    bpy.context.view_layer.update()

    def kept(o):
        return o.name in keep or o.name.split(".")[0] in keep or o.get("node")

    for o in list(bpy.context.scene.objects):
        p = o.parent
        if p is None or kept(p):
            continue
        while p is not None and not kept(p):
            p = p.parent
        mw = o.matrix_world.copy()
        o.parent = p
        o.matrix_world = mw
    bpy.context.view_layer.update()
    return root


def wheels(hull, ys, z, r, xmin, mat_prefix=None, hub_x=1.2, tris=None):
    """Cuts the road wheels out of hull into nodes wheel_1, wheel_2, ... (front axle first, left then right),
    each pivoting on its hub (axle along X), and gives them the move / idle clips (see wheel_clips).
    ys: axle positions along y; z, r: hub height and wheel radius; a face belongs to a wheel when its centroid
    is outboard of xmin and within r of the hub in the side view (and its material starts with mat_prefix), and
    none of its corners strays further (a long sliver left by decimation stays in the hull).
    Returns the wheel objects. Pair with FINISH keep=keep_with_wheels(...) and NLA_TRACKS export."""
    rules, hubs = {}, {}
    n = 0
    for y in sorted(ys, reverse=True):
        for side in (-1, 1):
            n += 1
            name = f"wheel_{n}"
            hubs[name] = (side * hub_x, y, z)
            rules[name] = (lambda c, m, vs, y=y, side=side:
                           side * c.x > xmin and (c.y - y) ** 2 + (c.z - z) ** 2 < r * r
                           and (mat_prefix is None or m.startswith(mat_prefix))
                           and all(side * v.x > xmin - 0.1 and (v.y - y) ** 2 + (v.z - z) ** 2 < (r * 1.08) ** 2
                                   for v in vs))
    parts = split(hull, rules, rest=hull.name, verts=True)
    out = []
    for name, hub in hubs.items():
        w = parts[name]
        w["node"] = True
        convert.pivot(w, hub)
        convert.parent(w, hull)
        out.append(w)
        if tris:
            convert.decimate(w, tris)
    wheel_clips(out)
    return out


# Export options for a wheeled unit: clips from NLA tracks, and the static idle clip kept (the exporter drops
# channels that never change unless told to keep them).
WHEEL_EXPORT = {"export_animation_mode": "NLA_TRACKS", "export_optimize_animation_keep_anim_object": True}


def wheel_names(axles):
    return tuple(f"wheel_{i + 1}" for i in range(2 * axles))


def keep_with_wheels(axles, *nodes):
    return ("hull", *nodes, *wheel_names(axles))


WHEEL_PERIOD = 15    # frames at 24 fps: one revolution in 0.625 s


def linear(action):
    """Sets every key of action LINEAR (new keys default to Bezier, which eases each quarter turn). Handles
    both the layered actions of Blender 4.4+ and the legacy fcurve list."""
    curves = list(getattr(action, "fcurves", None) or [])
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves += list(bag.fcurves)
    for fc in curves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"


def push(o, clip):
    """Moves o's active action onto a new NLA track named clip (the glTF clip name with NLA_TRACKS export)."""
    ad = o.animation_data
    action = ad.action
    action.name = f"{o.name}_{clip}"
    linear(action)
    track = ad.nla_tracks.new()
    track.name = clip
    track.strips.new(clip, 0, action)
    ad.action = None


def wheel_clips(objs):
    """move: each wheel rolls forward (top toward +Y = negative rotation about +X), LINEAR keys every 90 deg,
    one revolution per WHEEL_PERIOD frames, last key = first + 360 deg so it loops cleanly. idle: static."""
    for o in objs:
        for i in range(5):
            o.rotation_euler.x = -i * math.pi / 2
            o.keyframe_insert("rotation_euler", index=0, frame=i * WHEEL_PERIOD / 4)
        push(o, "move")
        o.rotation_euler.x = 0
        for f in (0, 24):
            o.keyframe_insert("rotation_euler", index=0, frame=f)
        push(o, "idle")
        o.rotation_euler.x = 0
