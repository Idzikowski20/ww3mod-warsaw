"""Shared helpers for the aircraft models (helicopters and jets), on top of convert.py and lib.py.

convert.load() joins a source into one mesh; helicopters need their rotors as separate nodes, so
load_parts() does the same freeze (skins, modifiers, transforms applied) but joins the source meshes into
several groups by source object name. place() then normalizes all the groups with one transform taken
from the body (rotor blades must not move the centre). spin() authors the rotor clips.
"""

import math
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import convert
from lib import mat

FPS = 96          # 0.25 s = 24 frames: a key every 90 degrees lands on a whole frame for main and tail
REV = 0.25        # seconds per main-rotor revolution
CLIPS = ("idle", "move")
HELI_KEEP = ("hull", "rotor", "tail_rotor")
NLA = {"export_animation_mode": "NLA_TRACKS"}


def load_parts(filename, group, drop=None):
    """Imports a source .glb and freezes every mesh in world space (as convert.load does), then joins them
    into groups. group(names) -> group name, where names is the mesh object's name followed by its
    ancestors' names (lower case); drop(names) -> True discards the mesh. Returns {group: object};
    the group objects are named after the group."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=convert.os.path.join(convert.SOURCES, filename))
    new = [o for o in bpy.data.objects if o not in before]
    dg = bpy.context.evaluated_depsgraph_get()
    groups = {}
    for o in new:
        if o.type != "MESH":
            continue
        names, p = [o.name.lower()], o.parent
        while p:
            names.append(p.name.lower())
            p = p.parent
        if drop and drop(names):
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        if not me.polygons:
            continue
        flat = bpy.data.objects.new(o.name, me)
        bpy.context.scene.collection.objects.link(flat)
        groups.setdefault(group(names) or "hull", []).append(flat)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    # lib.bake writes what the texture node gives into a Non-Color atlas the engine shows as it is, so read
    # the source textures as they are too (as sRGB they would be linearised and bake far too dark).
    for img in bpy.data.images:
        img.colorspace_settings.name = "Non-Color"
    out = {}
    for g, objs in groups.items():
        convert._join(objs)
        objs[0].name = g
        objs[0].data.name = g
        weld(objs[0])
        out[g] = objs[0]
    return out


def weld(o, angle=40):
    """Merges coincident vertices (a glTF source splits them at every seam and hard edge, so each triangle
    is its own piece: lib.bake's smart UV project then makes one sub-pixel island per triangle, which bakes
    black, and decimation cannot collapse across pieces). Hard edges come back from the face angle."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(o.data)
    bm.free()
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.set_sharp_from_angle(angle=math.radians(angle))


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def _pts(objs):
    return np.array([v.co[:] for o in objs for v in o.data.vertices])


def place(parts, front="-Y", length=None, rotor_diameter=None, body=None, rotor="rotor"):
    """One transform for every part: front turned to +Y, scaled so the body (the parts named, default all)
    is length metres long (or the main rotor rotor_diameter across), centred on x/y, lowest point on z = 0."""
    turn = {"+Y": 0, "-Y": 180, "+X": 90, "-X": -90}[front]
    objs = list(parts.values())
    m = Matrix.Rotation(-math.radians(turn), 4, "Z")
    for o in objs:
        o.data.transform(m)
    body = [parts[n] for n in body] if body else objs
    b = _pts(body)
    lo, hi = b.min(0), b.max(0)
    if rotor_diameter:
        r = _pts([parts[rotor]])
        hub = r.mean(0)
        k = rotor_diameter / (2 * np.sqrt(((r[:, :2] - hub[:2]) ** 2).sum(1)).max())
    elif length:
        k = length / (hi[1] - lo[1])
    else:
        k = 1.0
    c = (lo + hi) / 2
    t = Matrix.Scale(k, 4) @ Matrix.Translation((-c[0], -c[1], -lo[2]))
    for o in objs:
        o.data.transform(t)
    b = _pts(body)
    print(f"placed x {b[:, 0].min():.2f}..{b[:, 0].max():.2f} y {b[:, 1].min():.2f}..{b[:, 1].max():.2f} "
          f"z {b[:, 2].min():.2f}..{b[:, 2].max():.2f} (scale {k:.4f})")
    return k


def axis_pivot(o, hint, hub=None, axis=None):
    """Turns o into a spinning node: its origin moves to the rotor hub (the vertex mean, or hub) and its
    local Z to the disc normal (least-variance axis of its vertices, signed toward hint), geometry kept in
    place. axis forces the normal (two-blade rotors have no least-variance axis to find). Returns the hub."""
    p = _pts([o])
    centre = (p.min(0) + p.max(0)) / 2 if isinstance(hub, str) else np.array(hub) if hub is not None else p.mean(0)
    w, v = np.linalg.eigh(np.cov((p - p.mean(0)).T))
    n = Vector(axis).normalized() if axis else Vector(v[:, 0])
    if n.dot(Vector(hint)) < 0:
        n = -n
    rot = n.to_track_quat("Z", "Y").to_matrix().to_4x4()
    mw = Matrix.Translation(Vector(centre)) @ rot
    o.data.transform(mw.inverted())
    o.matrix_world = mw
    o.rotation_mode = "ZYX"   # local Z turns first: the key on rotation_euler.z spins about the disc normal
    o.rotation_euler = rot.to_euler("ZYX")
    print(f"{o.name}: hub {tuple(round(x, 2) for x in centre)} axis {tuple(round(x, 3) for x in n)}")
    return Vector(centre)


def spin(rotors):
    """Authors the idle and move clips: [(object, revolutions per REV, direction ±1), ...]. Keys every 90
    degrees, LINEAR, ending on a whole number of turns at REV seconds so the loop has no hitch. Each clip is
    a per-object action on an NLA track named after it (export with export_animation_mode NLA_TRACKS)."""
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 0, int(REV * FPS)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    for o, revs, sign in rotors:
        base = o.rotation_euler.z
        ad = o.animation_data_create()
        steps = 4 * revs
        for clip in CLIPS:
            act = bpy.data.actions.new(f"{o.name}_{clip}")
            ad.action = act
            for i in range(steps + 1):
                o.rotation_euler.z = base + sign * i * math.pi / 2
                o.keyframe_insert("rotation_euler", index=2, frame=i * REV * FPS / steps)
            ad.action = None
            track = ad.nla_tracks.new()
            track.name = clip
            track.strips.new(clip, 0, act)
        o.rotation_euler.z = base


def team_faces(o, pred, shade=0.9):
    """Gives o's faces whose centroid matches pred the player colour (material "team")."""
    m = mat("team", (shade, shade, shade))
    if m.name not in o.data.materials:
        o.data.materials.append(m)
    slot = list(o.data.materials).index(m)
    n = 0
    for p in o.data.polygons:
        if pred(p.center):
            p.material_index = slot
            n += 1
    print(f"team faces on {o.name}: {n}")


def delete_faces(o, pred):
    """Deletes o's faces whose centroid (mesh space) matches pred."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pred(f.calc_center_median())], context="FACES")
    bm.to_mesh(o.data)
    bm.free()


def wreck_rotor(o, keep_blades=(0,), blades=4, droop=0.5, hub_r=0.6, phase=0.0):
    """A broken rotor (o made by axis_pivot, so mesh space is the disc with Z the axis): only the blades in
    keep_blades survive past the hub, bent down by droop metres at the tip, each a little differently."""
    p = _pts([o])
    R = np.sqrt((p[:, :2] ** 2).sum(1)).max()
    sector = 2 * math.pi / blades

    def blade(c):
        a = (math.atan2(c.y, c.x) - phase) % (2 * math.pi)
        return int((a + sector / 2) // sector) % blades

    delete_faces(o, lambda c: math.hypot(c.x, c.y) > hub_r and blade(c) not in keep_blades)
    for v in o.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        if r > hub_r:
            i = blade(v.co)
            v.co.z -= droop * (1 + 0.6 * i) * ((r - hub_r) / (R - hub_r)) ** 2


def snap(o, pred, hinge, rot_deg, name="broken"):
    """Cuts the faces matching pred off o (a tail boom, a wing) and swings them about hinge by rot_deg
    (x, y, z degrees): a broken-off part still hanging on. Returns the piece (parented to o)."""
    parts = convert.split(o, {name: pred})
    piece = parts.get(name)
    if piece is None:
        return None
    convert.pivot(piece, hinge)
    piece.rotation_euler = [math.radians(d) for d in rot_deg]
    bpy.context.view_layer.update()
    convert.parent(piece, o)
    return piece


def paint(o, match, rgb):
    """Replaces the base colour of o's materials whose name contains match (lower case) with a flat
    rgb, e.g. a canopy whose glass texture would bake white."""
    for m in o.data.materials:
        if m is None or match not in m.name.lower() or not m.use_nodes:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        for link in list(bsdf.inputs["Base Color"].links):
            m.node_tree.links.remove(link)
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
        m.diffuse_color = (*rgb, 1)


def break_tail(hull, tail_rotor, cut_y, rot=(10, 0, 25)):
    """Wreck: the tail boom behind cut_y (and the tail rotor with it) snapped at the cut, drooping and
    turned aside."""
    piece = convert.split(hull, {"tail_boom": lambda c: c.y < cut_y}).get("tail_boom")
    if piece is None:
        return None
    p = _pts([piece])
    near = p[p[:, 1] > p[:, 1].max() - 0.6]   # the boom's end at the cut
    convert.pivot(piece, (float(np.median(near[:, 0])), cut_y, float(np.median(near[:, 2]))))
    if tail_rotor is not None:
        from lib import join
        tail_rotor.parent = None
        join(piece, tail_rotor)
    piece.rotation_euler = [math.radians(d) for d in rot]
    bpy.context.view_layer.update()
    convert.parent(piece, hull)
    return piece


def islands(o):
    """o's faces grouped into connected pieces (faces sharing a vertex position, so UV seams do not split
    a piece). Returns [(face indices, lo, hi)] with each piece's bounding box in mesh space."""
    co = np.array([v.co[:] for v in o.data.vertices])
    keys = {}
    vid = np.array([keys.setdefault(k, len(keys)) for k in map(tuple, np.round(co, 4))])
    parent = list(range(len(keys)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in o.data.polygons:
        vs = [vid[i] for i in p.vertices]
        r = find(vs[0])
        for v in vs[1:]:
            rv = find(v)
            if rv != r:
                parent[rv] = r
    pieces = {}
    for p in o.data.polygons:
        pieces.setdefault(find(vid[p.vertices[0]]), []).append(p.index)
    out = []
    for faces in pieces.values():
        vs = co[[i for f in faces for i in o.data.polygons[f].vertices]]
        out.append((faces, vs.min(0), vs.max(0)))
    return out


def split_faces(o, faces, name):
    """Moves the faces with those indices out of o into a new object called name (same origin)."""
    faces = set(faces)
    me = o.data.copy()
    for mesh, keep in ((me, faces), (o.data, None)):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.index in faces) != (keep is not None)],
                         context="FACES")
        bm.to_mesh(mesh)
        bm.free()
    part = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(part)
    part.matrix_world = o.matrix_world
    return part


def split_islands(o, rules):
    """Splits o by connected pieces: rules {name: predicate(lo, hi) -> bool} on each piece's bounding box
    (numpy arrays, mesh space), first match wins. Returns {name: object} for the names that got faces."""
    owner = {n: [] for n in rules}
    for faces, lo, hi in islands(o):
        n = next((n for n in rules if rules[n](lo, hi)), None)
        if n:
            owner[n] += faces
    order = list(range(len(o.data.polygons)))   # indices shift as faces leave o: map by the original order
    result = {}
    for n, faces in owner.items():
        if not faces:
            continue
        pos = {f: i for i, f in enumerate(order)}
        result[n] = split_faces(o, [pos[f] for f in faces], n)
        gone = set(faces)
        order = [f for f in order if f not in gone]
        print(f"split {n}: {len(faces)} faces")
    return result


def brighten(o, k):
    """Multiplies the base colour of o's textured materials by k (a source whose paint is too dark)."""
    for m in o.data.materials:
        if m is None or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
            continue
        src = bsdf.inputs["Base Color"].links[0].from_socket
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        a = next(x for x in mul.inputs if x.name == "A" and x.type == "RGBA")
        b = next(x for x in mul.inputs if x.name == "B" and x.type == "RGBA")
        nt.links.new(src, a)
        b.default_value = (k, k, k, 1)
        nt.links.new(next(x for x in mul.outputs if x.type == "RGBA"), bsdf.inputs["Base Color"])


def flatten_rotor(o, hub_r):
    """Straightens drooping blades (a parked rotor) into a flat disc: in the rotor's own frame (after
    axis_pivot) each vertex past hub_r is lifted by the blades' median sag at its radius."""
    co = np.array([v.co[:] for v in o.data.vertices])
    r = np.hypot(co[:, 0], co[:, 1])
    out = r > hub_r
    if out.sum() < 10:
        return
    edges = np.linspace(hub_r, r.max() + 1e-6, 16)
    mids, sag = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = (r >= a) & (r < b)
        if sel.any():
            mids.append((a + b) / 2)
            sag.append(np.median(co[sel, 2]))
    sag = np.array(sag) - sag[0]
    lift = np.interp(r, mids, sag, left=0.0)
    for i, v in enumerate(o.data.vertices):
        if out[i]:
            v.co.z -= lift[i]


JET_KEEP = ("hull",)


def wreck_jet(hull, wing_x, tail_y, rot=(6, -4, 14)):
    """Wreck of a fixed-wing aircraft: the right wing torn off past wing_x, the rear fuselage and tail
    behind tail_y cracked off and twisted."""
    delete_faces(hull, lambda c: c.x > wing_x)
    piece = convert.split(hull, {"tail": lambda c: c.y < tail_y}).get("tail")
    if piece is None:
        return
    p = _pts([piece])
    near = p[p[:, 1] > p[:, 1].max() - 0.8]
    convert.pivot(piece, (float(np.median(near[:, 0])), tail_y, float(np.median(near[:, 2]))))
    piece.rotation_euler = [math.radians(d) for d in rot]
    bpy.context.view_layer.update()
    convert.parent(piece, hull)
