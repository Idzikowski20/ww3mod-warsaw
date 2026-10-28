"""Shared helpers for the US vehicle models (abrams, bradley, humvee, m109, m270, HIMARS, strykershorad, m113).
Work-arounds for what convert.py does not do: load only some of a source's objects, and drop duplicated faces
(some sources carry every face twice, which doubles the triangles and blackens the baked AO)."""

import os
import bmesh
import bpy
from mathutils import Vector

import convert
from lib import box, cyl, mat


def load(filename, keep=None, name="hull", group=None):
    """convert.load, but only the source objects for which keep(object_name, lo, hi) is true
    (lo/hi: world bounding box in source units); the rest are deleted before the join.
    group(object_name, lo, hi) -> label tags each object's faces, for split(..., by group)."""
    keep = keep or (lambda n, lo, hi: True)
    labels = []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(convert.SOURCES, filename))
    new = [o for o in bpy.data.objects if o not in before]
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = []
    for o in new:
        if o.type != "MESH":
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        if not me.vertices:
            continue
        pts = [v.co for v in me.vertices]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        if not keep(o.name, lo, hi):
            bpy.data.meshes.remove(me)
            continue
        label = group(o.name, lo, hi) if group else None
        if label not in labels:
            labels.append(label)
        attr = me.attributes.new("grp", "INT", "FACE")
        attr.data.foreach_set("value", [labels.index(label)] * len(me.polygons))
        flat = bpy.data.objects.new(o.name, me)
        bpy.context.scene.collection.objects.link(flat)
        meshes.append(flat)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    convert._join(meshes)
    o = meshes[0]
    o.name = name
    o.data.name = name
    o["groups"] = [str(x) for x in labels]
    return o


def split(o, rules, rest=None):
    """convert.split, with predicates rule(centroid, group_label) (group labels from load(group=...))."""
    if rest:
        o.name = rest
    labels = list(o.get("groups", ["None"]))
    g = [0] * len(o.data.polygons)
    if "grp" in o.data.attributes:
        o.data.attributes["grp"].data.foreach_get("value", g)
    names = list(rules)
    owner = [next((i for i, n in enumerate(names) if rules[n](p.center, labels[g[k]])), -1)
             for k, p in enumerate(o.data.polygons)]
    out = {o.name: o}
    for i, n in enumerate(names + [None]):
        idx = {k for k, w in enumerate(owner) if w == (i if n else -1)}
        if n is None:
            part = o
        else:
            if not idx:
                print(f"split {n}: no faces matched")
                continue
            part = bpy.data.objects.new(n, o.data.copy())
            bpy.context.scene.collection.objects.link(part)
            out[n] = part
        bm = bmesh.new()
        bm.from_mesh(part.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in idx], context="FACES")
        bm.to_mesh(part.data)
        bm.free()
        print(f"split {part.name}: {len(idx)} faces")
    return out


def dedupe(o):
    """Deletes faces that repeat another face's corners exactly (same winding or reversed)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    seen = set()
    dup = []
    for f in bm.faces:
        k = tuple(sorted(tuple(round(c, 4) for c in v.co) for v in f.verts))
        if k in seen:
            dup.append(f)
        else:
            seen.add(k)
    bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
    bm.to_mesh(o.data)
    bm.free()
    print(f"dedupe {o.name}: {len(dup)} duplicate faces removed")


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def m2_50cal(name, parent, loc, material=None, rot_z=0.0):
    """M2 .50-calibre heavy machine gun, receiver at loc, barrel along +Y (1.65 m long overall)."""
    gun = mat("gunmetal", (0.11, 0.11, 0.1)) if material is None else material
    x, y, z = loc
    r = box(name, (0.13, 0.62, 0.16), (x, y, z), gun, parent=parent, bevel=0.01)
    cyl(name + "_jacket", 0.035, 0.42, (x, y + 0.5, z + 0.01), gun, axis="Y", segments=10, parent=parent)
    cyl(name + "_tube", 0.016, 0.72, (x, y + 1.05, z + 0.01), gun, axis="Y", segments=8, parent=parent)
    cyl(name + "_muzzle", 0.026, 0.07, (x, y + 1.42, z + 0.01), gun, axis="Y", segments=8, parent=parent)
    box(name + "_grips", (0.1, 0.1, 0.12), (x, y - 0.36, z - 0.02), gun, parent=parent)
    box(name + "_ammo", (0.12, 0.3, 0.2), (x - 0.15, y, z - 0.04), mat("olive", (0.25, 0.27, 0.16)), parent=parent)
    return r


def done(root):
    """Ends a build(): refreshes every object's world matrix. lib.finish() reads matrix_world to merge the
    helper parts into their node, and an object parented in this script still has a stale one until the
    view layer updates, which puts e.g. a turret-roof panel at the turret-local position in world space."""
    bpy.context.view_layer.update()
    return root


TAN = (0.42, 0.37, 0.27)      # CARC tan 686A as the Abrams source wears it
GREEN = (0.27, 0.30, 0.20)    # CARC green 383


def paint(o, rgb, gain=None, amount=0.8, only=None, flatten=0.0):
    """Repaints o's textured materials (all, or those whose texture image is in only): the texture's
    lightness times gain (gain ~ 1 / its mean lightness puts the average on rgb), tinted toward rgb by
    amount, keeping the source's own dirt and detail. For sources whose paint is near black or the wrong
    scheme (convert.recolor keeps the source lightness, too dark here). flatten (0..1) evens out the
    lightness (lightness ** (1 - flatten)), to fade a camouflage pattern into a plain coat. gain=None takes
    1 / the texture's own mean lightness, per texture."""
    lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
    done = set()
    for m in o.data.materials:
        if m is None or not m.use_nodes or m.name in done:
            continue
        done.add(m.name)
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
            continue
        src = bsdf.inputs["Base Color"].links[0].from_socket
        tex = src.node
        if tex.type != "TEX_IMAGE" or tex.image is None or (only is not None and tex.image.name not in only):
            continue

        def mix(blend, a, b, fac=1.0, clamp=True):
            n = nt.nodes.new("ShaderNodeMix")
            n.data_type = "RGBA"
            n.blend_type = blend
            n.clamp_result = clamp
            n.inputs["Factor"].default_value = fac
            for sock, v in (("A", a), ("B", b)):
                s = next(x for x in n.inputs if x.name == sock and x.type == "RGBA")
                if isinstance(v, tuple):
                    s.default_value = (*v, 1)
                else:
                    nt.links.new(v, s)
            return next(x for x in n.outputs if x.type == "RGBA")

        g = gain
        if g is None:
            import numpy as np
            px = np.array(tex.image.pixels[:], dtype=np.float32).reshape(-1, 4)
            g = 1.0 / max(float((px[:, :3] @ np.array([0.3, 0.59, 0.11], dtype=np.float32)).mean()), 0.03)
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(src, bw.inputs[0])
        k = g * lum
        base = mix("MULTIPLY", src, (k, k, k))
        light = nt.nodes.new("ShaderNodeMath")
        light.operation = "MULTIPLY"
        nt.links.new(bw.outputs[0], light.inputs[0])
        light.inputs[1].default_value = g
        even = nt.nodes.new("ShaderNodeMath")
        even.operation = "POWER"
        nt.links.new(light.outputs[0], even.inputs[0])
        even.inputs[1].default_value = 1.0 - flatten
        tinted = mix("MULTIPLY", even.outputs[0], tuple(rgb))
        nt.links.new(mix("MIX", base, tinted, amount), bsdf.inputs["Base Color"])


def erase_white(o, images, threshold=0.55, passes=40):
    """Paints out near-white markings (e.g. national crosses) painted into o's source textures named in
    images: each white pixel takes the mean of its non-white neighbours, growing inward pass by pass."""
    import numpy as np
    seen = set()
    for m in o.data.materials:
        if m is None or not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            im = n.image if n.type == "TEX_IMAGE" else None
            if im is None or im.name not in images or im.name in seen:
                continue
            seen.add(im.name)
            w, h = im.size
            px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
            rgb = px[..., :3]
            hole = rgb.min(axis=2) > threshold
            print(f"erase_white {im.name}: {int(hole.sum())} px")
            for _ in range(passes):
                if not hole.any():
                    break
                acc = np.zeros_like(rgb)
                cnt = np.zeros(hole.shape, dtype=np.float32)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ok = np.roll(~hole, (dy, dx), axis=(0, 1))
                    acc += np.roll(rgb, (dy, dx), axis=(0, 1)) * ok[..., None]
                    cnt += ok
                fill = hole & (cnt > 0)
                rgb[fill] = acc[fill] / cnt[fill][:, None]
                hole &= ~fill
            px[..., :3] = rgb
            im.pixels[:] = px.ravel()
            im.update()
            im.pack()


def recolor_flat(o, colors):
    """Sets the base colour of o's untextured materials named in colors {name: rgb} (a source painted in
    near-black linear values bakes black)."""
    for m in o.data.materials:
        if m is None or m.name not in colors:
            continue
        rgb = colors[m.name]
        m.diffuse_color = (*rgb, 1)
        if m.use_nodes:
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None and not bsdf.inputs["Base Color"].is_linked:
                bsdf.inputs["Base Color"].default_value = (*rgb, 1)


def turn(o, degrees, centre):
    """Rotates o's mesh about the vertical axis through centre (model metres), in place."""
    import math
    from mathutils import Matrix
    c = Vector(centre)
    o.data.transform(Matrix.Translation(c) @ Matrix.Rotation(math.radians(degrees), 4, "Z") @ Matrix.Translation(-c))


def weld(o, dist=1e-4):
    """Merges coincident vertices (a glTF import splits them at every UV seam), so that collapse decimation
    can work across the seams instead of shredding a triangle soup."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    print(f"weld {o.name}: {n} -> {len(bm.verts)} verts")
    bm.to_mesh(o.data)
    bm.free()


def drop_specks(o, size):
    """Deletes loose parts (connected pieces) whose bounding-box diagonal is under size metres: rivets and
    bolts by the thousand, which collapse decimation cannot thin out (it never deletes a whole piece)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    doomed = []
    pieces = 0
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, part = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop()
            part.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        pieces += 1
        lo = Vector((min(p.co.x for p in part), min(p.co.y for p in part), min(p.co.z for p in part)))
        hi = Vector((max(p.co.x for p in part), max(p.co.y for p in part), max(p.co.z for p in part)))
        if (hi - lo).length < size:
            doomed.extend(part)
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    print(f"drop_specks {o.name}: {pieces} pieces, {len(doomed)} verts of specks under {size} m removed")
    bm.to_mesh(o.data)
    bm.free()


# Wheels of wheeled vehicles: separate nodes wheel_<n>, pivot at the hub, spun by the "move" clip.
WHEEL_FPS = 40        # a key every 90 degrees = 6 frames at one revolution per 0.6 s
WHEEL_REV = 0.6       # seconds per wheel revolution
# The still "idle" clip has only constant channels, which the exporter drops unless told to keep them.
NLA = {"export_animation_mode": "NLA_TRACKS", "export_optimize_animation_size": False,
       "export_optimize_animation_keep_anim_object": True, "export_force_sampling": False}


def wheel_names(n):
    return tuple(f"wheel_{i}" for i in range(1, n + 1))


def spin_wheels(wheels):
    """Authors the "idle" (still) and "move" clips on the wheel nodes: each wheel turns about its axle (x)
    so that it rolls forward (+Y), one revolution per WHEEL_REV seconds, LINEAR keys every 90 degrees, the
    last key a whole turn on so the loop has no hitch. Each clip is a per-object action pushed to an NLA
    track named after it (export with NLA = export_animation_mode NLA_TRACKS)."""
    import math
    scene = bpy.context.scene
    scene.render.fps = WHEEL_FPS
    end = int(round(WHEEL_REV * WHEEL_FPS))
    scene.frame_start, scene.frame_end = 0, end
    for o in wheels:
        base = o.rotation_euler.x
        ad = o.animation_data_create()
        for clip, steps in (("idle", 1), ("move", 4)):
            act = bpy.data.actions.new(f"{o.name}_{clip}")
            ad.action = act
            for i in range(steps + 1):
                # Rolling forward along +Y with z up turns the wheel the negative way about +x.
                o.rotation_euler.x = base - (i * math.pi / 2 if clip == "move" else 0.0)
                o.keyframe_insert("rotation_euler", index=0, frame=i * end / steps)
            for fc in _fcurves(act):
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
            ad.action = None
            track = ad.nla_tracks.new()
            track.name = clip
            track.strips.new(clip, 0, act)
        o.rotation_euler.x = base


def _fcurves(act):
    """An action's F-curves (Blender 4.4+ keeps them in layers/strips/channelbags)."""
    if hasattr(act, "layers") and act.layers:
        return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags
                for fc in bag.fcurves]
    return list(getattr(act, "fcurves", []))


def split_axles(o, count):
    """Splits o (the wheels of one side) into count objects, one per wheel: its loose pieces are grouped by
    their centre along y, cut at the count - 1 widest gaps. Each part's origin goes to its bounding-box
    centre, the hub. Returns the parts front to back; o itself is removed."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    seen, pieces = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, idx = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            idx.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        ys = [v.co.y for i in idx for v in bm.faces[i].verts]
        pieces.append(((min(ys) + max(ys)) / 2, idx))
    bm.free()
    pieces.sort()
    cuts = sorted(sorted(range(1, len(pieces)), key=lambda i: pieces[i][0] - pieces[i - 1][0])[-(count - 1):])
    groups, start = [], 0
    for c in cuts + [len(pieces)]:
        groups.append({i for _, idx in pieces[start:c] for i in idx})
        start = c
    out = []
    for k, idx in enumerate(groups):
        part = bpy.data.objects.new(f"{o.name}_{k}", o.data.copy())
        bpy.context.scene.collection.objects.link(part)
        part.matrix_world = o.matrix_world
        bm = bmesh.new()
        bm.from_mesh(part.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in idx], context="FACES")
        bm.to_mesh(part.data)
        bm.free()
        lo, hi = convert.bounds(part)
        convert.pivot(part, (lo + hi) / 2)
        out.append(part)
    bpy.data.objects.remove(o, do_unlink=True)
    out.sort(key=lambda p: -p.matrix_world.translation.y)
    return out


def track_loop(name, x, width, front, rear, top, bottom, thickness, parent):
    """A track belt seen from the side, extruded to width at x: round the drive wheel front = (y, z, r),
    along the top at height top, round the idler rear = (y, z, r), and flat along the ground (bottom =
    (y_front, y_rear) of the ground run). One object, its outer faces given the engine's scrolling track
    texture by convert.track_belts. Hand-built running gear for tracked vehicles."""
    import convert
    from lib import join, prism
    fy, fz, fr = front
    ry, rz, rr = rear
    t = thickness
    outer = [(fy + fr + t, fz), (fy + 0.15, fz + fr + t - 0.04), (fy - fr, top), (ry + rr, top),
             (ry - 0.1, rz + rr + t - 0.02), (ry - rr - t, rz), (bottom[1], 0.0), (bottom[0], 0.0)]
    inner = [(fy + fr, fz), (fy + 0.15, fz + fr - 0.04), (fy - fr, top - t), (ry + rr, top - t),
             (ry - 0.1, rz + rr - 0.02), (ry - rr, rz), (bottom[1], t), (bottom[0], t)]
    edge = mat("belt_edge", (0.13, 0.12, 0.11))   # not "track*": that name keeps a material out of the bake
    segs = []
    for i in range(len(outer)):
        j = (i + 1) % len(outer)
        segs.append(prism(name, [outer[i], outer[j], inner[j], inner[i]][::-1], width, (0, 0, 0), edge))
    belt = join(segs[0], *segs[1:])
    belt.data.transform(convert.Matrix.Translation((x, 0, 0)))  # mesh x = model x: track_belts sides by it
    convert.weld(belt)
    # Only the outer (tread) faces scroll; the belt's side faces and inner faces keep the edge colour.
    convert.track_belts(belt, lambda c, n: abs(n.x) < 0.5 and Vector((0, n.y, n.z)).dot(
        Vector((0, c.y - (fy + ry) / 2, c.z - top / 2))) > 0)
    convert.parent(belt, parent)
    return belt
