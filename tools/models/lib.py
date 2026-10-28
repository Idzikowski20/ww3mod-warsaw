"""Model-building helpers for the unit glTFs (run inside Blender, see build.py).

Conventions the engine relies on (engine/OpenRA.Game/Graphics/Mesh.cs, WithMeshBody):
- metres, Z up, the front of the unit along +Y, origin on the ground under the centre;
- objects become glTF nodes and keep their names: a turret is an object named "turret"
  (parented to the hull), its gun an object named "barrel" parented to the turret;
- material "team*" is player colour (its colour is a shade, multiplied by the player colour),
  "outline*" is the inverted-hull outline shell, added by finish(), "track*" a track belt
  (convert.track_belts): its own tiling texture and UVs, not baked, scrolled by the engine.
"""

import math
import os
import tempfile
import bmesh
import bpy
from mathutils import Vector

OUTLINE = (0.07, 0.07, 0.06)
_materials = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _materials.clear()


def mat(name, rgb, rough=0.8):
    """A flat base-colour material, cached by name."""
    if name not in _materials:
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*rgb, 1)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = 0
        _materials[name] = m
    return _materials[name]


def _obj(name, bm, material, parent=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(material)
    o.location = loc
    if parent:
        o.parent = parent
    return o


def join(target, *others):
    """Merges meshes into target (keeping target's name, origin and parent)."""
    others = [o for o in others if o]
    if not others:
        return target
    with bpy.context.temp_override(active_object=target, selected_editable_objects=[target, *others]):
        bpy.ops.object.join()
    return target


def box(name, size, loc=(0, 0, 0), material=None, bevel=0.0, taper=None, parent=None, rot=None):
    """Box of size (x, y, z) centred at loc. taper=(top_x, top_y) scales the top face (sloped armour).
    bevel rounds the edges by that many metres."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
        if taper and v.co.z > 0:
            v.co.x *= taper[0]
            v.co.y *= taper[1]
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    if rot:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=_euler(rot))
    return _obj(name, bm, material or mat("grey", (0.5, 0.5, 0.5)), parent, loc)


def prism(name, profile, width, loc=(0, 0, 0), material=None, axis="X", parent=None, bevel=0.0):
    """Extrudes a 2D profile [(y, z), ...] (counter-clockwise, seen from +X) by width along X,
    centred. axis="Y" extrudes along Y with profile [(x, z), ...] instead. Hulls and glacis."""
    bm = bmesh.new()
    half = width / 2
    if axis == "X":
        a = [bm.verts.new((-half, y, z)) for y, z in profile]
        b = [bm.verts.new((half, y, z)) for y, z in profile]
    else:
        a = [bm.verts.new((x, half, z)) for x, z in profile]
        b = [bm.verts.new((x, -half, z)) for x, z in profile]
    n = len(profile)
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return _obj(name, bm, material or mat("grey", (0.5, 0.5, 0.5)), parent, loc)


def extrude(name, poly, height, loc=(0, 0, 0), material=None, top_scale=1.0, top_shift=(0, 0),
            parent=None, bevel=0.0):
    """Plan-view polygon [(x, y), ...] (counter-clockwise from above) extruded up by height from loc's z.
    top_scale shrinks the top toward the centroid and top_shift moves it, for sloped armour."""
    bm = bmesh.new()
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    bottom = [bm.verts.new((x, y, 0)) for x, y in poly]
    top = [bm.verts.new((cx + (x - cx) * top_scale + top_shift[0], cy + (y - cy) * top_scale + top_shift[1], height))
           for x, y in poly]
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return _obj(name, bm, material or mat("grey", (0.5, 0.5, 0.5)), parent, loc)


def cyl(name, radius, depth, loc=(0, 0, 0), material=None, axis="Z", segments=16, parent=None,
        radius2=None, bevel=0.0):
    """Cylinder (or cone with radius2) along axis, centred at loc."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius if radius2 is None else radius2, depth=depth)
    if bevel > 0:
        rim = [e for e in bm.edges if all(abs(abs(v.co.z) - depth / 2) < 1e-4 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=rim, offset=bevel, segments=1, affect="EDGES")
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=_euler((0, 90, 0)))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=_euler((90, 0, 0)))
    return _obj(name, bm, material or mat("grey", (0.5, 0.5, 0.5)), parent, loc)


def sphere(name, radius, loc=(0, 0, 0), material=None, scale=(1, 1, 1), parent=None, segments=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=radius)
    for v in bm.verts:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    return _obj(name, bm, material or mat("grey", (0.5, 0.5, 0.5)), parent, loc)


def _euler(deg):
    from mathutils import Euler
    return Euler([math.radians(d) for d in deg]).to_matrix()


def mirror_x(o):
    """Duplicate of o mirrored across x = 0 (left/right symmetric parts)."""
    c = o.copy()
    c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.location.x = -o.location.x
    bm = bmesh.new()
    bm.from_mesh(c.data)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(c.data)
    bm.free()
    c.name = o.name + "_r"
    return c


def strip_team(o):
    """No player colour on the models (the user's call, 2026-10-28): the unit marker shows the side. Faces with
    a "team" material get the part's main paint (the material covering most of its area) instead. Not deleted:
    on hand-built parts a team face can be structure, and deleting it would leave a hole."""
    if o.type != "MESH":
        return
    mats = list(o.data.materials)
    team = {i for i, m in enumerate(mats) if m and m.name.startswith("team")}
    if not team:
        return
    area = {}
    for p in o.data.polygons:
        if p.material_index not in team and mats[p.material_index] and not mats[p.material_index].name.startswith(("outline", "track")):
            area[p.material_index] = area.get(p.material_index, 0.0) + p.area
    if not area:
        return
    main = max(area, key=area.get)
    for p in o.data.polygons:
        if p.material_index in team:
            p.material_index = main


def outline(o, width):
    """Adds the inverted-hull outline to o: a copy pushed out along smoothed normals, faces flipped,
    material "outline". The engine draws only its inside, so it reads as a dark rim."""
    if o.type != "MESH" or not o.data.polygons:
        return
    m = mat("outline", OUTLINE)
    if m.name not in o.data.materials:
        o.data.materials.append(m)
    slot = list(o.data.materials).index(m)

    bm = bmesh.new()
    bm.from_mesh(o.data)
    shell = bmesh.new()
    shell.from_mesh(o.data)
    bmesh.ops.remove_doubles(shell, verts=shell.verts, dist=1e-4)
    shell.normal_update()
    for v in shell.verts:
        v.co += v.normal * width
    bmesh.ops.reverse_faces(shell, faces=shell.faces)
    for f in shell.faces:
        f.material_index = slot
    tmp = bpy.data.meshes.new("tmp")
    shell.to_mesh(tmp)
    shell.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    bm.to_mesh(o.data)
    bm.free()


def finish(path, outline_width=0.0, keep=("hull", "turret", "barrel"), texture_size=1024, wreck=False,
           flat=True, export_options=None):
    """Flattens every helper part into the nearest kept ancestor node (one draw per node in the engine),
    bakes one weathered albedo atlas for the model (burnt when wreck), adds outlines and exports a .glb.
    keep lists the node names that survive as glTF nodes; anything else is merged into its nearest
    kept ancestor, or into the first keep entry when it has none."""
    scene = bpy.context.scene
    # Parenting and locations set since the last depsgraph update are not in matrix_world yet.
    bpy.context.view_layer.update()
    for o in list(scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    keepers = [o for o in scene.objects if o.name in keep or o.name.split(".")[0] in keep
               or o.get("node")]
    def depth(o):
        return 0 if o.parent is None else 1 + depth(o.parent)

    # Deepest first, so a helper part parented to another helper part is merged before its parent goes.
    for o in sorted(scene.objects, key=depth, reverse=True):
        if o in keepers:
            continue
        target = o.parent
        while target and target not in keepers:
            target = target.parent
        if target is None:
            target = next(k for k in keepers if k.name == keep[0])
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        join(target, o)

    if flat:  # hand-built parts; a downloaded model keeps its own normals
        for o in keepers:
            for p in o.data.polygons:
                p.use_smooth = False
    for o in keepers:
        strip_team(o)
    if texture_size:
        bake(keepers, texture_size, os.path.splitext(os.path.basename(path))[0], wreck)
    if outline_width > 0:
        for o in keepers:
            outline(o, outline_width)

    # export_options adds to or overrides these, e.g. {"export_animation_mode": "NLA_TRACKS"} so that
    # same-named NLA tracks on several objects become one glTF clip (idle / move / attack).
    bpy.ops.export_scene.gltf(**{**dict(filepath=path, export_format="GLB", export_apply=True,
                                        export_yup=True, export_animations=True, export_materials="EXPORT",
                                        export_normals=True, export_texcoords=True),
                                 **(export_options or {})})


DUST = (0.36, 0.31, 0.23)


def _sock(sockets, name):
    """The colour socket of that name: a Mix node has float, vector and colour sockets all called A/B/Result."""
    return next(x for x in sockets if x.name == name and x.type == "RGBA")


def _weathering(m, base, wreck=False):
    """Turns material m into an emission of its colour weathered the way a vehicle in a ruined city is:
    crevice dirt (AO), mottled grime, rain streaks, worn edges, and dust and mud rising from the ground.
    base is an RGB tuple, or None to take the colour from the material's own base-colour texture
    (a downloaded model), read through its original UV map. wreck burns it: soot, scorch and rust.
    Baked to a texture by bake()."""
    m.use_nodes = True
    nt = m.node_tree
    source = None
    if base is None:
        # Keep the network feeding the base colour (texture, maybe a recolour), drop the rest.
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        source = bsdf.inputs["Base Color"].links[0].from_socket
        for n in list(nt.nodes):
            if n.type in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
                nt.nodes.remove(n)
    else:
        nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def node(kind, **inputs):
        n = N(kind)
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def math_(op, a, b=None, clamp=True):
        n = N("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    def mix(fac, a, b, blend="MIX"):
        n = N("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        if isinstance(fac, (int, float)):
            n.inputs["Factor"].default_value = fac
        else:
            L(fac, n.inputs["Factor"])
        for sock, v in (("A", a), ("B", b)):
            if isinstance(v, tuple):
                _sock(n.inputs, sock).default_value = (*v, 1)
            else:
                L(v, _sock(n.inputs, sock))
        return _sock(n.outputs, "Result")

    def scaled(c, k):
        return mix(1.0, c, (k, k, k), "MULTIPLY")

    if source is not None:
        # Texture nodes read the source UV map, not the new atlas map that bake() makes active. Their
        # images are read raw: as sRGB they would be linearised and then stored raw in the Non-Color atlas,
        # which the engine shows as is - about 4x too dark.
        for n in list(nt.nodes):
            if n.type == "TEX_IMAGE" and n.image:
                n.image.colorspace_settings.name = "Non-Color"
            if n.type == "TEX_IMAGE":
                uv = N("ShaderNodeUVMap")
                uv.uv_map = SOURCE_UV
                L(uv.outputs["UV"], n.inputs["Vector"])
        base = source
    else:
        base = tuple(base)

    coord = N("ShaderNodeTexCoord").outputs["Object"]
    grime = node("ShaderNodeTexNoise", Scale=3.5, Detail=8.0, Roughness=0.65)
    L(coord, grime.inputs["Vector"])
    streak_scale = N("ShaderNodeVectorMath")
    streak_scale.operation = "MULTIPLY"
    streak_scale.inputs[1].default_value = (9.0, 9.0, 0.8)
    L(coord, streak_scale.inputs[0])
    streaks = node("ShaderNodeTexNoise", Scale=2.0, Detail=4.0)
    L(streak_scale.outputs[0], streaks.inputs["Vector"])

    ao = node("ShaderNodeAmbientOcclusion", Distance=0.35)
    ao.samples = 16
    bevel = node("ShaderNodeBevel", Radius=0.012)
    geo = N("ShaderNodeNewGeometry")
    dot = N("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L(bevel.outputs["Normal"], dot.inputs[0])
    L(geo.outputs["Normal"], dot.inputs[1])
    edge = math_("MULTIPLY", math_("SUBTRACT", 1.0, dot.outputs["Value"]), 6.0)
    wear = math_("MULTIPLY", edge, math_("GREATER_THAN", grime.outputs["Fac"], 0.5))

    # Dust and mud by height above the ground (world z: the model stands on z = 0), so a turret
    # stays cleaner than the running gear whatever its own origin.
    sep = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs[0])
    low = math_("SUBTRACT", 1.0, math_("DIVIDE", sep.outputs["Z"], 1.1))
    dust = math_("MULTIPLY", math_("POWER", low, 2.0), math_("ADD", grime.outputs["Fac"], 0.2))

    c = mix(math_("MULTIPLY", math_("SUBTRACT", grime.outputs["Fac"], 0.3), 1.2), base, scaled(base, 0.62))
    c = mix(math_("MULTIPLY", math_("SUBTRACT", streaks.outputs["Fac"], 0.5), 0.8), c, scaled(base, 0.7))
    c = mix(math_("MULTIPLY", wear, 0.35), c, mix(1.0, scaled(base, 1.25), (0.04, 0.04, 0.04), "ADD"))
    c = mix(math_("MULTIPLY", dust, 0.55), c, DUST)

    if wreck:
        # Burnt out: everything charred dark, soot pooling in patches, rust blooming where paint burnt off.
        soot = node("ShaderNodeTexNoise", Scale=1.6, Detail=6.0, Roughness=0.7)
        L(coord, soot.inputs["Vector"])
        rust = node("ShaderNodeTexNoise", Scale=6.0, Detail=10.0, Roughness=0.7)
        L(coord, rust.inputs["Vector"])
        c = scaled(c, 0.42)
        c = mix(math_("MULTIPLY", math_("SUBTRACT", soot.outputs["Fac"], 0.35), 2.2), c, (0.03, 0.028, 0.026))
        c = mix(math_("MULTIPLY", math_("SUBTRACT", rust.outputs["Fac"], 0.55), 3.0), c, (0.26, 0.12, 0.05))

    shade = math_("ADD", 0.45, math_("MULTIPLY", ao.outputs["AO"], 0.55))
    lit = N("ShaderNodeMix")
    lit.data_type = "RGBA"
    lit.blend_type = "MULTIPLY"
    lit.inputs["Factor"].default_value = 1.0
    L(c, _sock(lit.inputs, "A"))
    L(shade, _sock(lit.inputs, "B"))

    emit = N("ShaderNodeEmission")
    L(_sock(lit.outputs, "Result"), emit.inputs["Color"])
    out = N("ShaderNodeOutputMaterial")
    L(emit.outputs[0], out.inputs["Surface"])
    return nt


SOURCE_UV = "source_uv"


def bake(objs, size, name, wreck=False):
    """Packs the UVs of every object in objs into one atlas and bakes their weathered colours into it
    (one texture per model). Team, outline and track materials are left as they are: player colour stays a flat
    tint the engine replaces, a track keeps its tiling texture and UVs. A downloaded model keeps its own texture
    as the colour source."""
    scene = bpy.context.scene
    for o in objs:
        uvs = o.data.uv_layers
        if len(uvs):
            uvs[0].name = SOURCE_UV
            for extra in list(uvs)[1:]:
                uvs.remove(extra)
        target = uvs.new(name="bake")
        uvs.active = target

    for other in scene.objects:
        other.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # Track faces stay out of the atlas: they keep their own UVs (copied back below).
    for o in objs:
        track = {i for i, m in enumerate(o.data.materials) if m and m.name.startswith("track")}
        if track:
            scene.tool_settings.mesh_select_mode = (False, False, True)
            bm = bmesh.from_edit_mesh(o.data)
            for f in bm.faces:
                if f.material_index in track:
                    f.select_set(False)
            bmesh.update_edit_mesh(o.data)
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Raw values: the engine shades in display space with no gamma step, so the texture must hold the
    # authored colours as they are, not converted from linear to sRGB.
    image = bpy.data.images.new(name + "_albedo", size, size)
    image.colorspace_settings.name = "Non-Color"
    baked = []
    copies = {}
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.name.startswith(("team", "outline", "track")):
                continue
            if m.name not in copies:
                bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.use_nodes else None
                textured = bsdf is not None and bsdf.inputs["Base Color"].is_linked
                color = tuple(bsdf.inputs["Base Color"].default_value[:3]) if bsdf is not None and not textured \
                    else tuple(m.diffuse_color[:3])
                copy = m.copy()
                nt = _weathering(copy, None if textured else color, wreck)
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.image = image
                nt.nodes.active = tex
                copies[m.name] = copy
            slot.material = copies[m.name]
            baked.append(slot)
    if not baked:
        return

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.device = "CPU"
    scene.render.bake.margin = 4
    # Cycles bakes every material into its active image node: the track tiles get a throwaway pixel instead.
    held = [(n, n.image) for o in objs for m in o.data.materials if m and m.name.startswith("track")
            for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]
    sink = bpy.data.images.new("bake_sink", 1, 1) if held else None
    for n, _ in held:
        n.image = sink
    bpy.ops.object.bake(type="EMIT")
    for n, img in held:
        n.image = img
    if sink:
        bpy.data.images.remove(sink)

    image.filepath_raw = os.path.join(tempfile.gettempdir(), image.name + ".png")
    image.file_format = "PNG"
    image.save()
    image.pack()

    out = bpy.data.materials.new(name + "_baked")
    out.use_nodes = True
    bsdf = next(n for n in out.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    tex = out.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    out.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    out.node_tree.nodes.active = tex
    for slot in baked:
        slot.material = out
    for o in objs:
        uvs = o.data.uv_layers
        if SOURCE_UV in uvs:
            mats = o.data.materials
            src, dst = uvs[SOURCE_UV].data, uvs["bake"].data
            for p in o.data.polygons:
                m = mats[p.material_index] if mats else None
                if m is not None and m.name.startswith("track"):
                    for li in p.loop_indices:
                        dst[li].uv = src[li].uv
            uvs.remove(uvs[SOURCE_UV])


def render_preview(glb, path, yaw=35, pitch=35, distance=13, size=640, target_z=1.0):
    """Cycles render of an exported .glb as the game lights it (sun from the south-east, baked textures,
    the outline shell showing only its inside), for checking a model without launching the game."""
    reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.device = "CPU"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.film_transparent = False
    # Display the values as they are, as the engine does (it lights in display space, no gamma step).
    scene.view_settings.view_transform = "Raw"
    for image in bpy.data.images:
        image.colorspace_settings.name = "Non-Color"

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.33, 0.34, 0.3, 1)
    scene.world = world

    # Every surface shaded exactly as engine/glsl/mesh.frag does it: albedo x (ambient + diffuse x n.L),
    # as an emission, with the same sun direction (glTF y-up (0.4, 1, 0.5) is Blender (0.4, -0.5, 1)).
    sun_dir = Vector((0.4, -0.5, 1.0)).normalized()
    for m in bpy.data.materials:
        if m.name.startswith("outline") or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
        factor = tuple(bsdf.inputs["Base Color"].default_value)
        if m.name.startswith("team"):
            factor = (0.85, 0.15, 0.12, 1)  # preview the player colour as red
        for n in list(nt.nodes):
            if tex is None or n.name != tex.name:
                nt.nodes.remove(n)
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = sun_dir
        nt.links.new(geo.outputs["Normal"], dot.inputs[0])
        lam = nt.nodes.new("ShaderNodeMath")
        lam.operation = "MULTIPLY_ADD"
        lam.use_clamp = False
        nt.links.new(dot.outputs["Value"], lam.inputs[0])
        lam.inputs[1].default_value = 0.55
        lam.inputs[2].default_value = 0.55
        floor = nt.nodes.new("ShaderNodeMath")
        floor.operation = "MAXIMUM"
        nt.links.new(lam.outputs[0], floor.inputs[0])
        floor.inputs[1].default_value = 0.55
        albedo = nt.nodes.new("ShaderNodeMix")
        albedo.data_type = "RGBA"
        albedo.blend_type = "MULTIPLY"
        albedo.inputs["Factor"].default_value = 1.0
        _sock(albedo.inputs, "A").default_value = factor
        if tex:
            nt.links.new(tex.outputs[0], _sock(albedo.inputs, "B"))
        else:
            _sock(albedo.inputs, "B").default_value = (1, 1, 1, 1)
        lit = nt.nodes.new("ShaderNodeMix")
        lit.data_type = "RGBA"
        lit.blend_type = "MULTIPLY"
        lit.inputs["Factor"].default_value = 1.0
        nt.links.new(_sock(albedo.outputs, "Result"), _sock(lit.inputs, "A"))
        nt.links.new(floor.outputs[0], _sock(lit.inputs, "B"))
        emit = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(_sock(lit.outputs, "Result"), emit.inputs[0])
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(emit.outputs[0], out.inputs["Surface"])

    # The outline shell: its near side (normals facing away from the camera) is see-through, as the
    # engine discards those fragments, leaving a dark rim round the silhouette.
    for m in bpy.data.materials:
        if not m.name.startswith("outline"):
            continue
        nt = m.node_tree
        nt.nodes.clear()
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        mixs = nt.nodes.new("ShaderNodeMixShader")
        dark = nt.nodes.new("ShaderNodeEmission")
        dark.inputs["Color"].default_value = (*OUTLINE, 1)
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(geo.outputs["Backfacing"], mixs.inputs[0])
        nt.links.new(dark.outputs[0], mixs.inputs[1])
        nt.links.new(clear.outputs[0], mixs.inputs[2])
        nt.links.new(mixs.outputs[0], out.inputs["Surface"])

    ground = bpy.data.objects.new("ground", bpy.data.meshes.new("ground"))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    bm.to_mesh(ground.data)
    bm.free()
    gm = bpy.data.materials.new("preview_ground")
    gm.use_nodes = True
    gm.node_tree.nodes.clear()
    ge = gm.node_tree.nodes.new("ShaderNodeEmission")
    ge.inputs["Color"].default_value = (0.24, 0.26, 0.2, 1)
    go = gm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    gm.node_tree.links.new(ge.outputs[0], go.inputs["Surface"])
    ground.data.materials.append(gm)
    scene.collection.objects.link(ground)

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    y, p = math.radians(yaw), math.radians(pitch)
    cam.location = (distance * math.cos(p) * math.sin(y), -distance * math.cos(p) * math.cos(y),
                    distance * math.sin(p) + target_z)
    direction = Vector((0, 0, target_z)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
