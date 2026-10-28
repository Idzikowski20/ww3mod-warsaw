"""CH-47F Chinook (actor TRAN), built by hand: no CC-BY source exists. Real size (Boeing CH-47F): fuselage
15.46 m long, 3.78 m wide over the sponsons, 5.68 m tall at the aft rotor head; two three-blade 18.29 m
rotors 11.94 m apart in tandem, the aft one on the tall aft pylon with a T55 turbine on each side of it;
fuel sponsons along the lower sides, four-wheel gear (twin wheels forward, single aft), rear loading
ramp under the upswept tail, cockpit glazing and cabin windows. US Army olive drab.
The rotors are the "rotor_front" and "rotor_rear" nodes (front turns counter-clockwise seen from above,
rear clockwise)."""

import math
import bmesh
import bpy
import convert
import lib
import _aircraft as A
from lib import box, cyl, mat, join

OLIVE = (0.28, 0.3, 0.2)
OLIVE_DARK = (0.21, 0.23, 0.15)
GLASS = (0.07, 0.09, 0.11)
RUBBER = (0.05, 0.05, 0.05)
METAL = (0.3, 0.3, 0.28)
BLADE = (0.13, 0.13, 0.12)
EXHAUST = (0.07, 0.065, 0.06)

FRONT_HUB = (0.0, 6.03, 4.55)
REAR_HUB = (0.0, -5.91, 5.4)
RADIUS = 9.145
HINGE = (0.0, -4.0, 0.6)       # where a wreck's aft section cracks off

# Fuselage cross-sections along y: (y, centre x, half width, bottom z, top z, top corner r, bottom corner r).
NOSE_CABIN = [
    (7.73, 0, 0.30, 1.40, 1.95, 0.28, 0.25),
    (7.55, 0, 0.75, 1.05, 2.45, 0.50, 0.40),
    (7.20, 0, 1.00, 0.80, 2.85, 0.55, 0.40),
    (6.60, 0, 1.18, 0.66, 3.20, 0.55, 0.35),
    (5.90, 0, 1.25, 0.60, 3.38, 0.55, 0.30),
    (-4.00, 0, 1.25, 0.60, 3.40, 0.55, 0.30),
]
RAMP = [  # the underside sweeps up to the tail: the loading ramp
    (-4.00, 0, 1.25, 0.60, 3.40, 0.55, 0.30),
    (-5.30, 0, 1.25, 1.05, 3.40, 0.55, 0.30),
    (-6.60, 0, 1.22, 1.75, 3.40, 0.55, 0.30),
    (-7.73, 0, 1.12, 2.45, 3.35, 0.40, 0.20),
]
AFT_PYLON = [
    (-3.00, 0, 0.35, 3.20, 3.45, 0.30, 0.05),
    (-3.90, 0, 0.72, 3.20, 4.45, 0.50, 0.05),
    (-6.40, 0, 0.78, 3.20, 4.85, 0.50, 0.05),
    (-7.50, 0, 0.65, 3.00, 4.60, 0.45, 0.05),
    (-7.90, 0, 0.40, 3.00, 4.10, 0.30, 0.05),
]
FRONT_PYLON = [
    (3.80, 0, 0.30, 3.25, 3.42, 0.15, 0.05),
    (4.80, 0, 0.62, 3.25, 3.95, 0.40, 0.05),
    (6.40, 0, 0.60, 3.15, 4.05, 0.40, 0.05),
    (7.10, 0, 0.35, 2.80, 3.40, 0.30, 0.05),
]


def _sponson(side):
    cx = side * 1.5
    return [
        (3.00, cx, 0.12, 1.05, 1.50, 0.10, 0.10),
        (2.60, cx, 0.36, 0.62, 1.95, 0.30, 0.20),
        (-3.40, cx, 0.36, 0.62, 1.95, 0.30, 0.20),
        (-3.90, cx, 0.20, 0.80, 1.70, 0.15, 0.15),
    ]


def _ring(cx, hw, zb, zt, rt, rb, n):
    """A rounded-rectangle section in the x-z plane, counter-clockwise from the bottom right corner."""
    rt = min(rt, hw, (zt - zb) / 2)
    rb = min(rb, hw, (zt - zb) / 2)
    pts = []
    for ccx, ccz, a0, r in ((cx + hw - rb, zb + rb, -90, rb), (cx + hw - rt, zt - rt, 0, rt),
                            (cx - hw + rt, zt - rt, 90, rt), (cx - hw + rb, zb + rb, 180, rb)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((ccx + r * math.cos(a), ccz + r * math.sin(a)))
    return pts


def loft(name, sections, material, parent=None, n=4):
    """A closed hull lofted through rounded-rectangle sections (see NOSE_CABIN)."""
    bm = bmesh.new()
    rings = [[bm.verts.new((x, y, z)) for x, z in _ring(cx, hw, zb, zt, rt, rb, n)]
             for y, cx, hw, zb, zt, rt, rb in sections]
    m = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return lib._obj(name, bm, material, parent)


def _rotor(name, hub, hull, blade_mat, metal, sign):
    """Hub, mast and three blades, origin at the hub."""
    rotor = cyl(name, 0.42, 0.32, hub, metal, segments=12, parent=hull)
    parts = [cyl("mast", 0.17, 0.6, (0, 0, -0.42), metal, segments=10, parent=rotor)]
    for k in range(3):
        a = math.radians(90 + 120 * k)
        rm = (0.5 + RADIUS) / 2
        parts.append(box("blade", (RADIUS - 0.5, 0.72, 0.07), (math.cos(a) * rm, math.sin(a) * rm, 0.04), blade_mat,
                         rot=(sign * 4, 0, math.degrees(a)), parent=rotor))
        parts.append(box("cuff", (0.9, 0.3, 0.16), (math.cos(a) * 0.8, math.sin(a) * 0.8, 0.04), metal,
                         rot=(0, 0, math.degrees(a)), parent=rotor))
    bpy.context.view_layer.update()
    join(rotor, *parts)
    return rotor


def build(wreck=False):
    olive = mat("olive", OLIVE)
    dark = mat("olive_dark", OLIVE_DARK)
    glass = mat("glass", GLASS)
    rubber = mat("rubber", RUBBER)
    metal = mat("metal", METAL)
    blade = mat("blade", BLADE)
    exhaust = mat("exhaust", EXHAUST)
    team = mat("team", (0.4, 0.4, 0.4) if wreck else (0.9, 0.9, 0.9))

    hull = loft("hull", NOSE_CABIN, olive, n=5)
    aft = [loft("ramp", RAMP, olive, parent=hull, n=5), loft("aft_pylon", AFT_PYLON, olive, parent=hull, n=5)]
    loft("front_pylon", FRONT_PYLON, olive, parent=hull, n=5)
    for side in (-1, 1):
        loft("sponson", _sponson(side), olive, parent=hull, n=4)

    # Aft pylon: a T55 turbine on each side, intake forward, exhaust aft, on a short strut.
    for side in (-1, 1):
        x = side * 1.25
        aft += [cyl("engine", 0.42, 2.6, (x, -5.5, 4.05), olive, axis="Y", segments=14, parent=hull),
                cyl("intake", 0.36, 0.4, (x, -4.0, 4.05), dark, axis="Y", segments=14, radius2=0.42, parent=hull),
                cyl("exhaust", 0.3, 0.5, (x, -7.0, 4.05), exhaust, axis="Y", segments=12, parent=hull),
                box("engine_strut", (0.5, 1.6, 0.3), (side * 0.85, -5.5, 4.05), dark, parent=hull)]
    # Rotor heads' fairings and masts' bases.
    box("front_head_fairing", (0.8, 1.0, 0.25), (0, FRONT_HUB[1], 4.05), dark, bevel=0.06, parent=hull)
    aft.append(box("rear_head_fairing", (0.9, 1.1, 0.3), (0, REAR_HUB[1], 4.9), dark, bevel=0.06, parent=hull))

    # Glazing: windshield, lower windshield, cockpit side windows, chin windows, cabin windows, crew door.
    box("windshield", (1.55, 0.75, 0.05), (0, 6.9, 3.06), glass, rot=(-30, 0, 0), parent=hull)
    box("windshield_low", (1.3, 0.5, 0.05), (0, 7.38, 2.67), glass, rot=(-49, 0, 0), parent=hull)
    for side in (-1, 1):
        box("cockpit_side", (0.05, 0.9, 0.7), (side * 1.13, 6.75, 2.45), glass, rot=(0, 0, side * 8), parent=hull)
        box("chin", (0.45, 0.3, 0.05), (side * 0.38, 7.48, 1.15), glass, rot=(55, 0, 0), parent=hull)
        for y in (3.6, 2.6, 1.6, 0.4, -0.6, -1.6, -2.7):
            box("window", (0.05, 0.42, 0.45), (side * 1.255, y, 2.35), glass, bevel=0.04, parent=hull)
    box("crew_door", (0.04, 0.9, 1.6), (1.26, 4.6, 1.75), dark, parent=hull)

    # Landing gear: twin wheels forward under the sponsons, single wheels aft.
    for side in (-1, 1):
        for dx in (-0.2, 0.2):
            cyl("wheel", 0.42, 0.24, (side * 1.5 + dx, 1.9, 0.42), rubber, axis="X", segments=12, parent=hull)
        box("gear_leg", (0.14, 0.2, 0.45), (side * 1.5, 1.9, 0.65), metal, parent=hull)
        aft.append(cyl("wheel_aft", 0.42, 0.28, (side * 1.55, -4.6, 0.42), rubber, axis="X", segments=12, parent=hull))
        aft.append(box("gear_aft", (0.5, 0.18, 0.18), (side * 1.3, -4.6, 0.6), metal, parent=hull))

    # Player colour: panels on both sides of the aft pylon, a roof panel and the front pylon's sides.
    for side in (-1, 1):
        aft.append(box("team_pylon", (0.03, 2.2, 0.7), (side * 0.79, -5.3, 3.95), team, parent=hull))
        box("team_front", (0.03, 1.1, 0.4), (side * 0.63, 5.4, 3.6), team, parent=hull)
    box("team_roof", (1.5, 2.4, 0.03), (0, 0.5, 3.415), team, parent=hull)

    front = _rotor("rotor_front", FRONT_HUB, hull, blade, metal, 1)
    rear = _rotor("rotor_rear", REAR_HUB, hull, blade, metal, -1)

    for o in bpy.context.scene.objects:   # smooth the round hull, keep the box edges hard
        if o.type == "MESH":
            for p in o.data.polygons:
                p.use_smooth = True
            o.data.set_sharp_from_angle(angle=math.radians(35))

    if wreck:
        A.wreck_rotor(front, keep_blades=(0, 1), blades=3, droop=1.6, hub_r=0.9, phase=math.radians(90))
        A.wreck_rotor(rear, keep_blades=(2,), blades=3, droop=2.2, hub_r=0.9, phase=math.radians(90))
        # The aft section (ramp, aft pylon, engines, rear rotor) cracked off behind the cabin, sagging and
        # twisted: swung about the hinge, then handed back to the hull with its new placement.
        crack = box("crack", (0.1, 0.1, 0.1), HINGE, dark, parent=hull)
        bpy.context.view_layer.update()
        for o in aft + [rear]:
            convert.parent(o, crack)
        crack.rotation_euler = (math.radians(7), math.radians(-5), math.radians(-9))
        bpy.context.view_layer.update()
        for o in aft + [rear]:
            convert.parent(o, hull)
        rear.name = "rotor_rear_wreck"     # no clip on a wreck: merged into the hull
        front.name = "rotor_front_wreck"
    else:
        A.spin([(front, 1, 1), (rear, 1, -1)])
    return hull


FINISH = {"flat": False, "keep": ("hull", "rotor_front", "rotor_rear"), "export_options": A.NLA}
PREVIEW = {"distance": 40, "target_z": 2.5}
