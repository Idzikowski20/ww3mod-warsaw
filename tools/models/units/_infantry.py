"""Shared builder for the infantry figures (every soldier, crew member and pilot module uses it).

The engine has no skinning, so a soldier is rigid parts: a rigged source figure is frozen in its posed
shape, every face goes to the segment of its dominant bone (by the vertex skin weights read before the
freeze), and each segment becomes its own node with its pivot at the joint:

    pelvis ─ torso ─ head
           │       ├ upperarm_l ─ forearm_l (with hand)
           │       └ upperarm_r ─ forearm_r (with hand) ─ weapon
           ├ thigh_l ─ calf_l (with foot)
           └ thigh_r ─ calf_r (with foot)

The clips idle / move / attack / death are Kevin Iglesias' soldier animations retargeted onto the
segments (class Clip); the weapon rides the right hand, its fore-grip turned toward the left palm every
frame. Each node's clip is pushed to an NLA track of that name (export_animation_mode NLA_TRACKS).

Workarounds of shared helpers (kept here rather than editing convert.py):
- convert.load drops armatures and joins the importer's bone-shape "Icosphere"; load_figure() reads the
  skin weights itself and _load() skips that sphere.
- convert.recolor multiplies the texture's grey by the colour, which leaves a near-black source (the
  US figure's black kit) black; tint() lifts the grey first.
- convert.decimate shatters dense hard-surface sources at infantry budgets; reduce() steps it, and
  load_prop(remesh=...) rebuilds the worst from voxels.

Sources: CC-BY-4.0 models and the Kevin Iglesias clips (Unity Asset Store EULA), credited in each unit
module's docstring and in tools/models/wiring/infantry-credits.md.
"""

import math
import os
from collections import Counter, defaultdict

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector, kdtree

import convert
from lib import join, mat

SEGMENTS = ("pelvis", "torso", "head", "upperarm_l", "forearm_l", "upperarm_r", "forearm_r",
            "thigh_l", "calf_l", "thigh_r", "calf_r")
PARENT = {"torso": "pelvis", "head": "torso", "upperarm_l": "torso", "upperarm_r": "torso",
          "forearm_l": "upperarm_l", "forearm_r": "upperarm_r", "thigh_l": "pelvis", "thigh_r": "pelvis",
          "calf_l": "thigh_l", "calf_r": "thigh_r", "weapon": "forearm_r"}
KEEP = SEGMENTS + ("weapon",)
FINISH = {"flat": False, "keep": KEEP, "texture_size": 512,
          "export_options": {"export_animation_mode": "NLA_TRACKS",
                             "export_optimize_animation_keep_anim_object": True}}
PREVIEW = {"distance": 5, "target_z": 0.95}

HEIGHT = 1.8          # metres, boots to helmet top
FIGURE_TRIS = 3700    # the figure; weapon and kit come on top, ≤ 5k in all
# Share of FIGURE_TRIS per segment (each arm / leg part gets its share once per side).
SHARE = {"pelvis": 0.13, "torso": 0.27, "head": 0.08, "upperarm": 0.04, "forearm": 0.06, "thigh": 0.06, "calf": 0.07}

# Faction colours for tint(): coyote / OCP tan, Russian EMR green.
COYOTE = (0.56, 0.47, 0.33)
EMR = (0.27, 0.33, 0.20)


# ---------------------------------------------------------------------------------------------------
# Figure


def bone_segment(name):
    """Segment of a bone, from its name (Character Creator CC_Base_* and Mixamo mixamorig:* rigs)."""
    n = name.lower()
    side = "_l" if ("_l_" in n or "left" in n) else "_r" if ("_r_" in n or "right" in n) else ""
    if side:
        if any(k in n for k in ("toe", "foot", "calf", "knee")) or ("leg" in n and "upleg" not in n):
            return "calf" + side
        if "thigh" in n or "upleg" in n:
            return "thigh" + side
        if any(k in n for k in ("forearm", "hand", "thumb", "index", "mid", "ring", "pinky", "elbow")):
            return "forearm" + side
        if "arm" in n:
            return "upperarm" + side
    if any(k in n for k in ("neck", "head", "facial", "jaw", "tongue", "teeth", "eye")):
        return "head"
    if any(k in n for k in ("spine", "waist", "ribs", "breast", "clavicle", "shoulder", "chest")):
        return "torso"
    return "pelvis"


class Figure:
    """segs: {segment: object}; joints: {name: Vector} in model space (shoulder_l, elbow_l, wrist_l, ...)."""

    def __init__(self, segs, joints):
        self.segs = segs
        self.joints = joints


def _freeze(o, dg):
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(o.matrix_world)
    return me


def _vertex_segments(o, bone_seg, index):
    """Per vertex: index of the segment holding most of its skin weight (-1 unweighted)."""
    names = {g.index: g.name for g in o.vertex_groups}
    out = []
    for v in o.data.vertices:
        acc = defaultdict(float)
        for g in v.groups:
            s = bone_seg.get(names[g.group])
            if s:
                acc[s] += g.weight
        out.append(index[max(acc, key=acc.get)] if acc else -1)
    return out


def drop_specks(o, size=0.03):
    """Deletes loose parts smaller than size metres across (buckles, rivets): invisible at game scale,
    and they stop the decimator, which cannot take an island below a few triangles."""
    convert.weld(o)   # a glTF import splits every vertex along UV and normal seams
    bm = bmesh.new()
    bm.from_mesh(o.data)
    seen, doomed = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        cos = [v.co for g in island for v in g.verts]
        span = max(max(c[i] for c in cos) - min(c[i] for c in cos) for i in range(3))
        if span < size:
            doomed.extend(island)
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(o.data)
    bm.free()


def load_figure(filename, skip=lambda o: False, frame=1, tris=FIGURE_TRIS, height=HEIGHT):
    """Imports a rigged figure, freezes it at frame, cuts it into the rigid segments by skin weight and
    returns a Figure facing +Y, height metres tall, standing on z = 0 with the hips over the origin.
    skip(object) drops source meshes (a figure's own gun, its eyes)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(convert.SOURCES, filename))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    arm = next(o for o in new if o.type == "ARMATURE")
    bone_seg = {b.name: bone_segment(b.name) for b in arm.data.bones}
    head = {pb.name: arm.matrix_world @ pb.head for pb in arm.pose.bones}

    # Joint of each segment: the head of its first bone whose parent is in another segment.
    # Twist / share helper bones only when a segment has no other root (CC_Base_NeckTwist01).
    joint = {}
    for helpers in (False, True):
        for b in arm.data.bones:
            s = bone_seg[b.name]
            low = b.name.lower()
            if s in joint or helpers != ("twist" in low or "share" in low):
                continue
            if b.parent is None or bone_seg[b.parent.name] != s:
                joint[s] = head[b.name]
    for side in "lr":
        hand = next(b.name for b in arm.data.bones if bone_seg[b.name] == "forearm_" + side
                    and "hand" in b.name.lower()
                    and not any(k in b.name.lower() for k in ("thumb", "index", "mid", "ring", "pinky")))
        joint["wrist_" + side] = head[hand]
        foot = next(b.name for b in arm.data.bones if bone_seg[b.name] == "calf_" + side
                    and "foot" in b.name.lower() and "toe" not in b.name.lower())
        joint["ankle_" + side] = head[foot]
    joint["pelvis"] = (joint["thigh_l"] + joint["thigh_r"]) / 2

    index = {s: i for i, s in enumerate(SEGMENTS)}
    pieces, points, owners = [], [], []
    for o in new:
        if o.type != "MESH" or o.name.startswith("Icosphere") or not o.data.polygons or skip(o):
            continue
        vseg = None
        if o.vertex_groups and any(m.type == "ARMATURE" for m in o.modifiers):
            vseg = _vertex_segments(o, bone_seg, index)
            share = Counter(vseg).most_common(1)[0][1] / max(1, len(vseg))
            if share < 0.85 and sum(len(p.vertices) - 2 for p in o.data.polygons) < 4000:
                # A low-poly garment spread over several segments: subdivide first, so the cut between segments follows
                # the joint instead of jagging along big triangles (weights interpolate onto new vertices).
                sub = o.modifiers.new("cut", "SUBSURF")
                sub.subdivision_type = "SIMPLE"
                sub.levels = 2
                with bpy.context.temp_override(object=o, active_object=o):
                    bpy.ops.object.modifier_move_to_index(modifier=sub.name, index=0)
                    bpy.ops.object.modifier_apply(modifier=sub.name)
                vseg = _vertex_segments(o, bone_seg, index)
        me = _freeze(o, dg)
        if vseg is not None and len(vseg) != len(me.vertices):
            vseg = None
        fseg = []
        for p in me.polygons:
            votes = Counter(vseg[i] for i in p.vertices if vseg[i] >= 0) if vseg else None
            fseg.append(votes.most_common(1)[0][0] if votes else -1)
        if vseg:
            for v, s in zip(me.vertices, vseg):
                if s >= 0:
                    points.append(v.co.copy())
                    owners.append(s)
        piece = bpy.data.objects.new(o.name + "_frozen", me)
        bpy.context.scene.collection.objects.link(piece)
        pieces.append((piece, fseg))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)

    # Unskinned parts (pouches, patches hung on the scene root) go to the segment of the nearest skinned vertex.
    tree = kdtree.KDTree(len(points))
    for i, p in enumerate(points):
        tree.insert(p, i)
    tree.balance()
    for piece, fseg in pieces:
        attr = piece.data.attributes.new("seg", "INT", "FACE")
        for i, p in enumerate(piece.data.polygons):
            s = fseg[i]
            if s < 0:
                s = owners[tree.find(p.center)[1]]
            attr.data[i].value = s
    objs = [p for p, _ in pieces]
    convert._join(objs)
    body = objs[0]
    convert.raw_colours(body)

    # Facing +Y, hips over the origin, on the ground, height metres tall.
    lo, hi = convert.bounds(body)
    pv = joint["pelvis"]
    k = height / (hi.z - lo.z)
    m = Matrix.Scale(k, 4) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Translation((-pv.x, -pv.y, -lo.z))
    body.data.transform(m)
    joints = {n: m @ p for n, p in joint.items()}

    segs = {}
    for s in SEGMENTS:
        i = index[s]
        me = body.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        layer = bm.faces.layers.int["seg"]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != i], context="FACES")
        bm.to_mesh(me)
        bm.free()
        part = bpy.data.objects.new(s, me)
        bpy.context.scene.collection.objects.link(part)
        segs[s] = part
    bpy.data.objects.remove(body, do_unlink=True)

    for s, o in segs.items():
        drop_specks(o)
        convert.decimate(o, int(SHARE[s[:-2] if s.endswith(("_l", "_r")) else s] * tris))
        o.rotation_mode = "QUATERNION"
    for s, o in segs.items():
        convert.pivot(o, joints[s])
    for s in SEGMENTS[1:]:
        convert.parent(segs[s], segs[PARENT[s]])
    joints.update({"shoulder_" + x: joints["upperarm_" + x] for x in "lr"})
    joints.update({"elbow_" + x: joints["forearm_" + x] for x in "lr"})
    joints["top"] = convert.bounds(segs["head"])[1].z
    return Figure(segs, joints)


def tint(objs, rgb, amount=0.9, lift=0.8, gain=1.5, only=lambda m: True):
    """Recolours the textured materials of objs toward rgb, keeping the texture's light and dark:
    colour = mix(texture, rgb x (lift + gain x grey), amount). Lifts a near-black source (where
    convert.recolor would stay black). only(material) picks the materials to touch."""
    done = set()
    for o in objs:
        for m in o.data.materials:
            if m is None or m.name in done or not m.use_nodes or not only(m):
                continue
            done.add(m.name)
            nt = m.node_tree
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None:
                continue
            base = bsdf.inputs["Base Color"]
            if not base.is_linked:
                c = base.default_value
                grey = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
                v = lift + gain * grey
                base.default_value = tuple(c[i] * (1 - amount) + rgb[i] * v * amount for i in range(3)) + (1,)
                continue
            src = base.links[0].from_socket
            bw = nt.nodes.new("ShaderNodeRGBToBW")
            nt.links.new(src, bw.inputs[0])
            lifted = nt.nodes.new("ShaderNodeMath")
            lifted.operation = "MULTIPLY_ADD"
            nt.links.new(bw.outputs[0], lifted.inputs[0])
            lifted.inputs[1].default_value = gain
            lifted.inputs[2].default_value = lift
            col = nt.nodes.new("ShaderNodeMix")
            col.data_type = "RGBA"
            col.blend_type = "MULTIPLY"
            col.inputs["Factor"].default_value = 1.0
            sock = lambda n, name, out=False: next(x for x in (n.outputs if out else n.inputs)
                                                   if x.name == name and x.type == "RGBA")
            nt.links.new(lifted.outputs[0], sock(col, "A"))
            sock(col, "B").default_value = (*rgb, 1)
            blend = nt.nodes.new("ShaderNodeMix")
            blend.data_type = "RGBA"
            blend.inputs["Factor"].default_value = amount
            nt.links.new(src, sock(blend, "A"))
            nt.links.new(sock(col, "Result", True), sock(blend, "B"))
            nt.links.new(sock(blend, "Result", True), base)


# ---------------------------------------------------------------------------------------------------
# Weapons and kit


def _load(filename, name):
    """convert.load without the importer's bone-shape sphere (it joins it into the model)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(convert.SOURCES, filename))
    new = [o for o in bpy.data.objects if o not in before]
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = []
    for o in new:
        if o.type == "MESH" and not o.name.startswith("Icosphere") and o.data.polygons:
            flat = bpy.data.objects.new(o.name, _freeze(o, dg))
            bpy.context.scene.collection.objects.link(flat)
            meshes.append(flat)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    convert._join(meshes)
    o = meshes[0]
    o.name = o.data.name = name
    return o


def cut(o, keep):
    """Deletes the faces whose centre (mesh space) fails keep(Vector): stray parts of a source."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context="FACES")
    bm.to_mesh(o.data)
    bm.free()


weld = convert.weld


def reduce(o, tris):
    """Decimates harder than convert.decimate holds up to: welds the seams, dissolves near-flat detail
    first, then collapses in steps (one big collapse turns a dense hard-surface model into shards)."""
    weld(o)
    count = lambda: sum(len(p.vertices) - 2 for p in o.data.polygons)
    if count() <= tris:
        return
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(4), verts=bm.verts, edges=bm.edges,
                             delimit={"UV", "MATERIAL"})
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    while count() > tris * 1.05:
        before = count()
        convert.decimate(o, max(tris, int(before * 0.4)))
        if count() >= before * 0.97:
            break


def load_prop(filename, length, front="-Y", keep=None, tris=600, name="weapon", axis="length", turn=(),
              specks=0.012, trim=None, remesh=None):
    """A downloaded weapon or piece of kit: stray parts cut by keep (source coordinates), turned by turn
    [(axis, degrees), ...] in order (a source lying askew), its front turned to +Y, length metres long
    along y (axis="height": that tall, "width": that wide), centred, bottom on z = 0, loose bits under
    specks metres dropped, decimated."""
    o = _load(filename, name)
    convert.raw_colours(o)
    if keep:
        cut(o, keep)
    for ax, deg in turn:
        o.data.transform(Matrix.Rotation(math.radians(deg), 4, ax))
    if axis == "height":
        convert.normalize(o, front=front, height=length)
    elif axis == "width":
        convert.normalize(o, front=front, width=length)
    else:
        convert.normalize(o, front=front, length=length)
    if trim:
        cut(o, trim)
    if specks:
        drop_specks(o, specks)
    if remesh:
        # A source too dense and fragmented to decimate (it shatters): rebuild its surface from voxels
        # of remesh = (size m, colour) and paint it one flat colour (the voxel surface has no UVs).
        size, rgb = remesh
        mod = o.modifiers.new("remesh", "REMESH")
        mod.mode = "VOXEL"
        mod.voxel_size = size
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=mod.name)
        o.data.materials.clear()
        o.data.materials.append(mat(name + "_flat", rgb))
    reduce(o, tris)
    return o


# Weapons: source, real length, where the source's muzzle points, a keep box (source units) cutting strays,
# and two points in the normalized weapon (muzzle +Y, centred on y, bottom z = 0), as (y, z):
# grip = right hand, fore = left hand.
def _box(x0, x1, y0, y1, z0, z1):
    return lambda c: x0 < c.x < x1 and y0 < c.y < y1 and z0 < c.z < z1


DARK = (0.11, 0.11, 0.10)      # flat colour of the voxel-rebuilt black guns
OLIVE = (0.30, 0.31, 0.22)

WEAPONS = {
    "m4": dict(file="m4_carbine.glb", length=0.84, front="-Y", keep=_box(-0.6, 0.6, -5, 5, -2, 2),
               grip=(-0.15, 0.10), fore=(0.03, 0.19)),
    "ak": dict(file="ak47.glb", length=0.88, front="+Y", keep=_box(-50, 50, -470, 440, -100, 130),
               grip=(-0.18, 0.09), fore=(0.06, 0.18)),
    # Under-barrel grenade launchers: the launcher's barrel and receiver (its own grip and stock cut off)
    # fitted under the rifle's handguard, top at z, centred on y (rifle space).
    "m4_m320": dict(base="m4", under=dict(file="m320_grenade_launcher_low-poly.glb", length=0.35, front="-Y",
                                          trim=lambda c: c.y > -0.07 and 0.11 < c.z < 0.2, at=(0.10, 0.165), tris=160)),
    "ak_gp25": dict(base="ak", under=dict(file="low-poly_gp-25.glb", length=0.32, front="+X",
                                          at=(0.12, 0.15), tris=160)),
    # The M249 source shatters when decimated: rebuilt from voxels, one flat colour; bipod legs cut.
    "m249": dict(file="m249__diy_builds_2.glb", length=1.04, front="-X", keep=_box(-1, 1, -1, 0, -1, 1),
                 remesh=(0.006, DARK), trim=lambda c: not (0.2 < c.y < 0.36 and c.z < 0.27),
                 grip=(-0.19, 0.19), fore=(0.12, 0.20)),
    "pkm": dict(file="pkm_machine_gun.glb", length=1.19, front="-Y", grip=(-0.285, 0.09), fore=(-0.02, 0.12)),
    "m110": dict(file="kac_m110.glb", length=1.1, front="+X", grip=(-0.24, 0.09), fore=(0.12, 0.16)),
    "svd": dict(file="svd_dragunov.glb", length=1.22, front="+Y", grip=(-0.30, 0.09), fore=(0.15, 0.13)),
    "mp5": dict(file="mp5.glb", length=0.68, front="+X", turn=(("Z", -38.4), ("Y", -5.4)),
                grip=(-0.06, 0.12), fore=(0.12, 0.17)),
    "javelin": dict(file="fgm-148_javelin.glb", length=1.2, front="+Y", turn=(("X", 21.6),),
                    grip=(-0.30, 0.12), fore=(0.02, 0.22)),
    "stinger": dict(file="fim-92_stinger_v2.glb", length=1.52, front="+X", grip=(-0.14, 0.09), fore=(0.12, 0.19)),
    "flamer": dict(build="wand", grip=(0.0, 0.0), fore=(0.30, 0.02)),
    "tablet": dict(build="tablet", grip=(0.0, 0.0), fore=(0.26, 0.0)),
}

# Kit carried on the body: source, size (metres along its length axis), front, keep / remesh as for weapons.
KIT = {
    # The AT4 source (1.3M-triangle open scan) neither decimates nor voxel-rebuilds: an AT4 built by hand.
    "at4": dict(build="at4"),
    "rpg": dict(file="rpg-7.glb", length=1.32, front="-X", tris=350),
    "mortar": dict(file="mortar_-_m224.glb", length=0.75, specks=0.03, front="-Y", axis="height", remesh=(0.012, DARK), tris=350),
    "radio": dict(file="militarytactical_radio__backpack.glb", length=0.5, front="-Y", axis="height",
                  remesh=(0.01, OLIVE), tris=300),
    "medbag": dict(file="medical_kit_bag.glb", length=0.34, front="-Y", axis="width", tris=250),
    # The flame-thrower source's tanks shatter (a flat sheet is left): the pack is built by hand too.
    "tanks": dict(build="tanks"),
    "headset": dict(file="tactical_headset_pilot.glb", length=0.21, front="-Y", axis="width", tris=500),
}


def _tablet(name):
    """Drone controller / tablet, built by hand: a slab 26 cm wide along +Y (right palm at y = 0, left
    palm at its far end), screen up."""
    from lib import box
    o = box(name, (0.17, 0.30, 0.025), (0, 0.13, 0), mat("tablet_case", (0.16, 0.17, 0.14)), bevel=0.006)
    join(o, box("screen", (0.13, 0.21, 0.004), (0, 0.13, 0.013), mat("tablet_screen", (0.18, 0.32, 0.36))),
         box("stick_l", (0.02, 0.02, 0.03), (0.04, 0.27, 0.02), mat("tablet_case", (0.16, 0.17, 0.14))),
         box("stick_r", (0.02, 0.02, 0.03), (0.04, -0.01, 0.02), mat("tablet_case", (0.16, 0.17, 0.14))))
    return o


def _wand(name):
    """Flame-thrower wand, built by hand (the source's lies tangled with its hose): tube along +Y from the
    rear grip (origin) to the nozzle, with a fore-grip."""
    from lib import box, cyl
    metal = mat("wand_metal", (0.20, 0.21, 0.17))
    o = cyl(name, 0.022, 0.78, (0, 0.22, 0.05), metal, axis="Y", segments=8)
    join(o, cyl("nozzle", 0.03, 0.12, (0, 0.62, 0.05), metal, axis="Y", segments=8, radius2=0.022),
         box("grip_r", (0.025, 0.04, 0.11), (0, 0.0, 0.0), mat("wand_grip", (0.12, 0.11, 0.09))),
         box("grip_f", (0.025, 0.04, 0.10), (0, 0.30, 0.0), mat("wand_grip", (0.12, 0.11, 0.09))),
         cyl("valve", 0.03, 0.06, (0, -0.2, 0.05), metal, axis="Y", segments=8))
    return o


def _at4(name):
    """AT4 launcher, built by hand: olive tube along +Y with its end caps, sights and shoulder stop."""
    from lib import box, cyl
    olive = mat("at4_olive", (0.36, 0.36, 0.26))
    black = mat("at4_black", (0.10, 0.10, 0.09))
    o = cyl(name, 0.042, 1.02, (0, 0, 0), olive, axis="Y", segments=10)
    join(o, cyl("cap_f", 0.047, 0.05, (0, 0.49, 0), black, axis="Y", segments=10),
         cyl("cap_r", 0.05, 0.07, (0, -0.48, 0), black, axis="Y", segments=10),
         box("sight_f", (0.012, 0.03, 0.05), (-0.03, 0.18, 0.06), black),
         box("sight_r", (0.03, 0.03, 0.04), (-0.03, -0.12, 0.06), black),
         box("stop", (0.03, 0.05, 0.07), (0, -0.25, -0.07), black))
    return o


def _tanks(name):
    """Flame-thrower pack, built by hand: two fuel tanks and a pressure tank between them on a frame."""
    from lib import box, cyl, sphere
    olive = mat("tank_olive", (0.30, 0.31, 0.21))
    steel = mat("tank_frame", (0.16, 0.16, 0.14))
    o = cyl(name, 0.07, 0.52, (-0.085, 0, 0), olive, segments=10)
    join(o, cyl("tank_r", 0.07, 0.52, (0.085, 0, 0), olive, segments=10),
         sphere("tank_air", 0.065, (0, -0.04, 0.05), olive, segments=10),
         box("frame", (0.3, 0.02, 0.03), (0, 0.06, -0.2), steel),
         box("frame_t", (0.3, 0.02, 0.03), (0, 0.06, 0.2), steel),
         cyl("valve_l", 0.015, 0.04, (-0.085, 0, 0.28), steel, segments=6),
         cyl("valve_r", 0.015, 0.04, (0.085, 0, 0.28), steel, segments=6))
    return o


def load_kit(key, name, tris=None):
    k = KIT[key]
    if "build" in k:
        return {"at4": _at4, "tanks": _tanks}[k["build"]](name)
    return load_prop(k["file"], k["length"], k["front"], k.get("keep"), tris or k["tris"], name,
                     k.get("axis", "length"), k.get("turn", ()), k.get("specks", 0.012), k.get("trim"),
                     k.get("remesh"))


def weapon(key, tris=700, name="weapon"):
    """Loads WEAPONS[key] (an under-barrel launcher fitted to its base rifle) with its origin moved to the
    grip; returns (object, spec)."""
    spec = WEAPONS[key]
    if "base" in spec:
        u = spec["under"]
        spec = dict(WEAPONS[spec["base"]], under=u)
        o = load_prop(spec["file"], spec["length"], spec["front"], spec.get("keep"), tris, name)
        gl = load_prop(u["file"], u["length"], u["front"], u.get("keep"), u["tris"], "under", trim=u.get("trim"))
        lo, hi = convert.bounds(gl)
        gl.data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, u["at"][0] - (lo.y + hi.y) / 2, u["at"][1] - hi.z)))
        join(o, gl)
    elif "build" in spec:
        o = {"tablet": _tablet, "wand": _wand}[spec["build"]](name)
    else:
        o = load_prop(spec["file"], spec["length"], spec["front"], spec.get("keep"), tris, name,
                      turn=spec.get("turn", ()), specks=spec.get("specks", 0.012), trim=spec.get("trim"),
                      remesh=spec.get("remesh"))
    gy, gz = spec["grip"]
    o.data.transform(Matrix.Translation((0, -gy, -gz)))
    return o, spec


def _m(loc, q=None):
    m = Matrix.Translation(loc)
    return m @ q.to_matrix().to_4x4() if q is not None else m


def aim_rotation(d, up=Vector((0, 0, 1))):
    """Rotation taking +Y to direction d and keeping +Z as near up as it can."""
    y = Vector(d).normalized()
    z = (up - y * up.dot(y)).normalized()
    return Matrix((y.cross(z), y, z)).transposed().to_quaternion()


PALM = 0.08            # wrist to the middle of the palm, metres

# Motion: Kevin Iglesias, "Human Soldier Animations 2.0 FREE" (Unity Asset Store EULA), FBX clips.
# Each clip is sampled bone by bone and our rigid segments follow the same world rotations (with a
# rest-pose offset per segment, as his rig rests in a T-pose). For idle and move the arms come from a
# weapon-hold pose (in Unity a masked layer over the clip); attack and death are whole-body clips.
KEVIN = os.path.join(convert.SOURCES, "unzipped", "human-soldier-animations", "Animations", "Male")
CLIPS = {
    "idle": "Idles/HumanM@MilitaryIdle01.fbx",
    "move": "Movement/Walk/HumanM@Walk01_Forward.fbx",
    "death": "Combat/HumanM@Death01.fbx",
    "unarmed": "Idles/HumanM@Idle01.fbx",
}
GRIPS = {   # hold kind: (weapon-hold pose, attack clip)
    "rifle": ("../Masked Poses/HumanM@WeaponHold_AssaultRifle01.fbx", "Combat/AssaultRifle/HumanM@AssaultRifle_Aim01_Shoot01.fbx"),
    "long": ("../Masked Poses/HumanM@WeaponHold_Rifle01.fbx", "Combat/Rifle/HumanM@Rifle_Aim01_Shoot01.fbx"),
    "launcher": ("../Masked Poses/HumanM@WeaponHold_Bazooka01.fbx", "Combat/Bazooka/HumanM@Bazooka_Aim01_Shoot01.fbx"),
}
BONES = {"pelvis": "B-hips", "torso": "B-chest", "head": "B-head", "upperarm_l": "B-upperArm.L",
         "forearm_l": "B-forearm.L", "upperarm_r": "B-upperArm.R", "forearm_r": "B-forearm.R",
         "thigh_l": "B-thigh.L", "calf_l": "B-shin.L", "thigh_r": "B-thigh.R", "calf_r": "B-shin.R"}
ARM_BONES = ("shoulder", "upperArm", "forearm", "hand")   # taken from the hold pose


def _frame(side, up):
    """Rotation whose x is side (made square to up), z is up."""
    u = up.normalized()
    s = (side - u * side.dot(u)).normalized()
    return Matrix((s, u.cross(s), u)).transposed()


def _rot(m):
    return m.to_3x3().normalized().to_quaternion()


class Clip:
    """One Kevin Iglesias clip sampled frame by frame: world rotations of the mapped bones and the hips'
    position, in our model frame (x right, y forward, z up), and the rest pose they are relative to."""

    def __init__(self, path, hold=None):
        rig, act = self._import(path)
        held = {}
        if hold:
            hrig, hact = self._import(hold)
            bpy.context.scene.frame_set(1)
            held = {pb.name: pb.matrix_basis.copy() for pb in hrig.pose.bones
                    if any(pb.name.startswith("B-" + b) for b in ARM_BONES)}
            self._drop(hrig, hact)
        mw, bones = rig.matrix_world.copy(), rig.data.bones   # copy: the clip also keys the rig object
        world = lambda m: mw @ m
        rest = {b.name: world(b.matrix_local) for b in bones}
        head = lambda n: rest[n].translation
        up = head("B-neck") - head("B-hips")
        right = head("B-upperArm.R") - head("B-upperArm.L")
        right = (right - up.normalized() * right.dot(up.normalized())).normalized()
        upn = up.normalized()
        self.conv = Matrix((right, upn.cross(right), upn))           # rows: his world -> our frame
        conv_q = self.conv.to_quaternion()
        self.to_ours = lambda q: conv_q @ q @ conv_q.inverted()
        self.vec = lambda v: self.conv @ v
        self.rest = {n: self.to_ours(_rot(m)) for n, m in rest.items()}
        self.rest_pos = {n: self.vec(m.translation) for n, m in rest.items()}
        self.rest_tail = {b.name: self.vec(mw @ b.tail_local) for b in bones}
        self.hip_height = self.rest_pos["B-hips"].z - min(self.rest_pos[n].z for n in ("B-toe.L", "B-foot.L"))

        start, end = act.frame_range
        self.frames = []
        for f in range(int(start), int(math.floor(end)) + 1):
            bpy.context.scene.frame_set(f)
            basis = {pb.name: held.get(pb.name, pb.matrix_basis) for pb in rig.pose.bones}
            basis["B-root"] = Matrix()   # the FBX keys its root with the x100 / -90° unit conversion
            pose = {}
            for b in bones:   # forward kinematics in the armature's space (parents come first)
                local = b.matrix_local if b.parent is None else b.parent.matrix_local.inverted() @ b.matrix_local
                pose[b.name] = (pose[b.parent.name] if b.parent else Matrix()) @ local @ basis[b.name]
            self.frames.append({n: (self.to_ours(_rot(world(m))), self.vec(world(m).translation))
                                for n, m in pose.items()})
        self.fps = bpy.context.scene.render.fps
        self._drop(rig, act)

    @staticmethod
    def _import(path):
        before = set(bpy.data.objects)
        acts = set(bpy.data.actions)
        bpy.ops.import_scene.fbx(filepath=os.path.normpath(os.path.join(KEVIN, path)))
        rig = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
        act = next(a for a in bpy.data.actions if a not in acts)
        rig.animation_data.action = act
        return rig, act

    @staticmethod
    def _drop(rig, act):
        for o in [rig, *rig.children_recursive]:
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.actions.remove(act)


def _fk(base, rots, pelvis_loc):
    """World matrices of every segment from world rotations rots and the pelvis position."""
    out = {}
    for s in SEGMENTS:
        if s == "pelvis":
            out[s] = _m(pelvis_loc, rots[s])
        else:
            out[s] = out[PARENT[s]] @ Matrix.Translation(base[s].translation) @ \
                (rots[PARENT[s]].inverted() @ rots[s]).to_matrix().to_4x4()
    return out


class Soldier:
    """A figure plus what it holds, animated from the Kevin Iglesias clips."""

    def __init__(self, fig, held=None, spec=None, hold="rifle"):
        self.fig, self.held, self.spec, self.hold = fig, held, spec, hold
        j = fig.joints
        self.base = {"pelvis": _m(j["pelvis"])}
        for s in SEGMENTS[1:]:
            self.base[s] = _m(j[s] - j[PARENT[s]])
        if held is not None:
            held.rotation_mode = "QUATERNION"
            bpy.context.view_layer.update()
            convert.parent(held, fig.segs["forearm_r"])
        self.objs = dict(fig.segs, **({"weapon": held} if held is not None else {}))
        self.palm = {}
        for side in "lr":
            wr, e0 = j["wrist_" + side], j["elbow_" + side]
            self.palm[side] = wr + (wr - e0).normalized() * PALM - e0      # in the forearm's own space

    def _offsets(self, clip):
        """Per segment, the world rotation taking our rest segment onto his rest bone."""
        j, r, t = self.fig.joints, clip.rest_pos, clip.rest_tail
        a = {"pelvis": _frame(j["thigh_l"] - j["thigh_r"], j["torso"] - j["pelvis"]),
             "torso": _frame(j["shoulder_l"] - j["shoulder_r"], j["head"] - j["torso"])}
        k = {"pelvis": _frame(r["B-thigh.L"] - r["B-thigh.R"], r["B-spine"] - r["B-hips"]),
             "torso": _frame(r["B-upperArm.L"] - r["B-upperArm.R"], r["B-neck"] - r["B-spine"])}
        off = {s: (k[s] @ a[s].inverted()).to_quaternion() for s in a}
        off["head"] = off["torso"]
        ends = {"upperarm": ("shoulder", "elbow"), "forearm": ("elbow", "wrist"),
                "thigh": ("thigh", "calf"), "calf": ("calf", "ankle")}
        for s in SEGMENTS[3:]:
            kind, side = s[:-2], s[-1]
            p, q = ends[kind]
            ours = j[q + "_" + side] - j[p + "_" + side]
            bone = BONES[s]
            off[s] = ours.rotation_difference(t[bone] - r[bone])
        return off

    def sample(self, clip, frames=None, loop=False):
        """[(seconds, {node: local Matrix})] following clip frame by frame."""
        off = self._offsets(clip)
        scale = (self.fig.joints["pelvis"].z) / clip.hip_height
        hips0 = clip.rest_pos["B-hips"]
        frames = clip.frames if frames is None else frames
        if loop:
            frames = frames + frames[:1]
        out = []
        for i, fr in enumerate(frames):
            rots = {s: fr[BONES[s]][0] @ clip.rest[BONES[s]].inverted() @ off[s] for s in SEGMENTS}
            d = (fr["B-hips"][1] - hips0) * scale
            world = _fk(self.base, rots, self.fig.joints["pelvis"] + d)
            local = {"pelvis": world["pelvis"]}
            for s in SEGMENTS[1:]:
                local[s] = world[PARENT[s]].inverted() @ world[s]
            if self.held is not None:
                local["weapon"] = world["forearm_r"].inverted() @ self._weapon(world)
            out.append((i / clip.fps, local))
        return out

    def _weapon(self, world):
        """The weapon's world matrix: grip in the right palm, its fore-grip toward the left palm."""
        pr = world["forearm_r"] @ self.palm["r"]
        pl = world["forearm_l"] @ self.palm["l"]
        gy, gz = self.spec["grip"]
        fy, fz = self.spec["fore"]
        tilt = Quaternion((1, 0, 0), -math.atan2(fz - gz, fy - gy))
        return _m(pr, aim_rotation(pl - pr) @ tilt)

    def key(self, clip, samples, interp="LINEAR"):
        """Keys every node through samples [(seconds, {node: local Matrix})] and pushes each node's action
        to an NLA track named clip (one glTF animation per clip with export_animation_mode NLA_TRACKS)."""
        fps = bpy.context.scene.render.fps
        for name, o in self.objs.items():
            prev = None
            for t, pose in samples:
                loc, q, _ = pose[name].decompose()
                if prev is not None and prev.dot(q) < 0:
                    q = -q
                prev = q
                o.location, o.rotation_quaternion = loc, q
                o.keyframe_insert("location", frame=t * fps)
                o.keyframe_insert("rotation_quaternion", frame=t * fps)
            ad = o.animation_data
            act = ad.action
            act.name = f"{clip}_{name}"
            for fc in _fcurves(act):
                for kp in fc.keyframe_points:
                    kp.interpolation = interp
            track = ad.nla_tracks.new()
            track.name = clip
            strip = track.strips.new(clip, 0, act)
            if getattr(act, "slots", None) and hasattr(strip, "action_slot") and strip.action_slot is None:
                strip.action_slot = act.slots[0]
            ad.action = None

    def animate(self):
        """idle, move (loops), attack (once per shot), death; the scene runs at the clips' 25 fps."""
        bpy.context.scene.render.fps = 25
        hold, shoot = GRIPS[self.hold] if self.held is not None else (None, None)
        idle = Clip(CLIPS["idle"] if hold else CLIPS["unarmed"], hold)
        self.key("idle", self.sample(idle, loop=True))
        self.key("move", self.sample(Clip(CLIPS["move"], hold)))
        if shoot:
            self.key("attack", self.sample(Clip(shoot)))
        else:   # unarmed: a short stretch of the idle
            self.key("attack", self.sample(idle, idle.frames[:12]))
        self.key("death", self.sample(Clip(CLIPS["death"])))
        bpy.context.scene.frame_set(0)   # bake (dust by height) and export standing: every clip starts upright
        rest = self.sample(idle, idle.frames[:1])[0][1]
        for name, m in rest.items():   # the nodes' own transforms (glTF rest): first idle frame
            loc, q, _ = m.decompose()
            self.objs[name].location, self.objs[name].rotation_quaternion = loc, q


def _fcurves(act):
    """An action's F-curves: legacy Action.fcurves, or the slotted layers / channel bags (Blender 4.4+)."""
    if hasattr(act, "fcurves"):
        try:
            return list(act.fcurves)
        except (AttributeError, RuntimeError):
            pass
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


# ---------------------------------------------------------------------------------------------------
# Assembly


def _mats(o, *keys):
    return any(m is not None and any(k in m.name.lower() for k in keys) for m in o.data.materials)


def _under(o, *prefixes):
    p = o.parent
    while p is not None:
        if p.name.startswith(prefixes):
            return True
        p = p.parent
    return False


FIGURES = {
    # Character Creator rig, black kit: tinted coyote / OCP tan (but its sunglasses).
    "america": dict(file="soldier_full_tactical_gear.glb", skip=lambda o: _mats(o, "eye", "helmet"),
                    tint=COYOTE, keep_colour=("glus",), helmet=(0.50, 0.43, 0.31), rails=True),
    # Mixamo rig holding its own Krinkov (dropped: the AK is fitted instead), tinted toward EMR green.
    "russia": dict(file="fsb_operator.glb",
                   skip=lambda o: _under(o, "Gun_") or _mats(o, "eye", "helmet", "night_vis"),
                   tint=EMR, keep_colour=("face", "fsb_patch", "gloves", "boots"), helmet=(0.29, 0.33, 0.21)),
}


def helmet(fig, rgb, rails=False):
    """A combat helmet built by hand over the figure's head (the sources' own helmets fall apart below
    ~1000 triangles): a dome fitted to the skull, with side rails and a night-vision mount when rails.
    Parented to the head."""
    from lib import box, sphere
    bpy.context.view_layer.update()
    head = fig.segs["head"]
    pts = [head.matrix_world @ v.co for v in head.data.vertices]
    top = max(p.z for p in pts)
    skull = [p for p in pts if p.z > top - 0.10]
    xs, ys = [p.x for p in skull], [p.y for p in skull]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2 - 0.01
    rx, ry, rz = (max(xs) - min(xs)) / 2 + 0.03, (max(ys) - min(ys)) / 2 + 0.035, 0.115
    cz = top + 0.025 - rz
    shell = mat("helmet_%02x%02x%02x" % tuple(int(c * 255) for c in rgb), rgb)
    dome = sphere("helmet", 1.0, (cx, cy, cz), shell, segments=14)
    cut(dome, lambda c: c.z > -0.3)
    dome.data.transform(Matrix.Diagonal((rx, ry, rz, 1)))
    parts = [dome]
    if rails:
        for side in (-1, 1):
            parts.append(box("rail", (0.012, ry * 1.1, 0.02), (cx + side * rx * 0.93, cy - 0.01, cz + 0.005), shell))
        parts.append(box("nvg_mount", (0.045, 0.02, 0.035), (cx, cy + ry * 0.97, cz + 0.01), shell))
    bpy.context.view_layer.update()
    for o in parts:
        convert.parent(o, head)
    return dome


def headset(fig):
    """The pilot's headset (tactical_headset_pilot.glb) over the head, ear cups on the ears."""
    o = load_kit("headset", "headset")
    bpy.context.view_layer.update()
    head = fig.segs["head"]
    pts = [head.matrix_world @ v.co for v in head.data.vertices]
    top = max(p.z for p in pts)
    skull = [p for p in pts if p.z > top - 0.10]
    cx = sum(p.x for p in skull) / len(skull)
    cy = sum(p.y for p in skull) / len(skull)
    lo, hi = convert.bounds(o)
    o.data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -hi.z)))
    o.location = (cx, cy - 0.01, top + 0.012)
    bpy.context.view_layer.update()
    convert.parent(o, head)
    return o


def carry(fig, o, segment="torso", rot=(0, 0, 0), height=0.25, side=0.0, front=False):
    """Hangs a piece of kit o on a segment: centred, rotated rot (degrees XYZ), its face against the
    figure's back (front=True: chest) at height metres above the segment's joint, side metres to the right.
    finish() would merge it into that segment's node; soldier() merges it before the clips are keyed."""
    from mathutils import Euler
    lo, hi = convert.bounds(o)
    o.data.transform(Euler([math.radians(r) for r in rot]).to_matrix().to_4x4() @
                     Matrix.Translation(-(lo + hi) / 2))
    lo, hi = convert.bounds(o)
    bpy.context.view_layer.update()
    seg = fig.segs[segment]
    z = fig.joints[segment].z + height
    pts = [seg.matrix_world @ v.co for v in seg.data.vertices]
    near = [p for p in pts if abs(p.z - z) < 0.08 and abs(p.x - side) < 0.12] or pts
    if front:
        y = max(p.y for p in near) - lo.y - 0.01
    else:
        y = min(p.y for p in near) - hi.y + 0.01
    o.location = (side, y, z)
    bpy.context.view_layer.update()
    convert.parent(o, seg)
    return o


def in_hand(fig, o, side="r", drop=0.0):
    """Hangs o (top centre) from the palm of a hand: a tool bag carried at the side."""
    j = fig.joints
    wr, e0 = j["wrist_" + side], j["elbow_" + side]
    palm = wr + (wr - e0).normalized() * PALM
    lo, hi = convert.bounds(o)
    o.data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -hi.z)))
    o.location = palm - Vector((0, 0, drop))
    bpy.context.view_layer.update()
    convert.parent(o, fig.segs["forearm_" + side])
    return o


def shovel(name="shovel"):
    """Entrenching tool, built by hand: handle along +Y, blade at its end."""
    from lib import box, cyl
    wood = mat("shovel_handle", (0.36, 0.29, 0.19))
    steel = mat("shovel_blade", (0.24, 0.26, 0.22))
    o = cyl(name, 0.016, 0.62, (0, 0, 0), wood, axis="Y", segments=6)
    join(o, box("blade", (0.17, 0.22, 0.012), (0, 0.41, 0), steel, taper=None),
         box("grip", (0.11, 0.025, 0.025), (0, -0.31, 0), wood))
    return o


def tool_bag(name="tool_bag"):
    """Canvas tool bag with a handle, built by hand."""
    from lib import box
    canvas = mat("tool_bag", (0.33, 0.30, 0.21))
    o = box(name, (0.14, 0.38, 0.22), (0, 0, 0), canvas, bevel=0.02)
    join(o, box("handle", (0.03, 0.16, 0.06), (0, 0, 0.13), mat("tool_bag_strap", (0.12, 0.12, 0.10))))
    return o


def soldier(side, gun=None, hold="rifle", regular=True, kit=None, skip=None, headgear="helmet",
            helmet_rgb=None, tris=FIGURE_TRIS):
    """Builds a whole soldier: figure of side ("america" / "russia"), tinted to the regulars' camouflage
    unless regular is False (special forces keep the source colours), gun from WEAPONS held as hold
    ("rifle", "long" or "launcher": which Kevin Iglesias hold pose and attack clip), headgear "helmet"
    (built by hand) or "headset" (pilots), kit(figure) hangs extra pieces; then the clips. Returns the
    root (pelvis)."""
    f = FIGURES[side]
    fig = load_figure(f["file"], skip=lambda o: f["skip"](o) or bool(skip and skip(o)), tris=tris)
    if regular:
        tint(fig.segs.values(), f["tint"],
             only=lambda m: not any(k in m.name.lower() for k in f["keep_colour"]))
    held, spec = weapon(gun) if gun else (None, None)
    s = Soldier(fig, held, spec, hold)
    if headgear == "helmet":
        helmet(fig, helmet_rgb or f["helmet"], f.get("rails", False))
    else:
        headset(fig)
    if kit:
        kit(fig)
    # Merge the kit into its segments now, while every transform is fresh: finish() would merge it after
    # the clips are keyed, with the scene left mid-clip, and misplace it.
    bpy.context.view_layer.update()
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH" and o.name not in KEEP and o.parent is not None and o.parent.name in KEEP:
            join(o.parent, o)
    s.animate()
    return fig.segs["pelvis"]
