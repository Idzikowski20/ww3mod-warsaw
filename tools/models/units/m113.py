"""M113A3 armoured personnel carrier, built by hand (no CC-BY/CC0 source exists): an aluminium box hull
4.86 m long overall (with the A3's two external rear fuel tanks), 2.69 m wide over the tracks, 1.83 m to
the roof; five dual road wheels a side, front drive sprocket, rear idler, folded trim vane on the glacis,
rear ramp, driver's hatch front left, engine louvres front right, large cargo hatch behind, and the
commander's cupola with an M2 .50 cal behind a gun shield (the turret node). Track belts carry the
scrolling track texture (convert.track_belts; tools/models/wiring/tracks-credits.md)."""

import math

import _usveh
from lib import box, cyl, mat, prism

ROOF = 1.83
BELLY = 0.43
NOSE = (2.15, 1.05)                # glacis foot (y, z)
BROW = (0.95, ROOF)                # glacis top
REAR = -2.2                        # rear plate
HULL_W, LOWER_W = 2.5, 1.86
TRACK_X, TRACK_W, TRACK_T = 1.15, 0.38, 0.06
ROAD_Y = (1.12, 0.42, -0.28, -0.98, -1.68)
WHEEL_R = 0.305
WHEEL_Z = WHEEL_R + TRACK_T
SPROCKET = (1.78, 0.6, 0.27)
IDLER = (-2.02, 0.5, 0.27)
RING = (0.25, -0.15, ROOF)         # commander's cupola

GLACIS = (BROW[0] - NOSE[0], BROW[1] - NOSE[1])
_L = math.hypot(*GLACIS)
_N = (GLACIS[1] / _L, -GLACIS[0] / _L)   # outward normal of the glacis (up and forward)
SLOPE = math.degrees(math.atan2(GLACIS[1], -GLACIS[0]))


def _on_glacis(t, off=0.0):
    """Point (y, z) a fraction t up the glacis from its foot, off metres out from it."""
    return (NOSE[0] + GLACIS[0] * t + _N[0] * off, NOSE[1] + GLACIS[1] * t + _N[1] * off)


def _hull(paint, dark, glass):
    hull = prism("hull", [(REAR, 0.95), (1.9, 0.95), NOSE, BROW, (REAR, ROOF)], HULL_W, material=paint,
                 bevel=0.03)
    prism("lower_hull", [(REAR + 0.05, BELLY), (1.7, BELLY), (NOSE[0] - 0.03, 0.98), (REAR + 0.05, 0.98)],
          LOWER_W, material=paint, parent=hull)
    # Trim vane folded down on the glacis, with its stiffening ribs and hinge arms.
    a, b = _on_glacis(0.06, 0.05), _on_glacis(0.88, 0.05)
    a2, b2 = _on_glacis(0.88, 0.09), _on_glacis(0.06, 0.09)
    prism("trim_vane", [a, b, a2, b2], 2.3, material=paint, parent=hull)
    for t in (0.25, 0.5, 0.75):
        y, z = _on_glacis(t, 0.11)
        box("vane_rib", (2.2, 0.06, 0.04), (0, y, z), paint, parent=hull, rot=(SLOPE, 0, 0))
    for s in (-1, 1):
        y, z = _on_glacis(0.9, 0.07)
        box("vane_arm", (0.08, 0.3, 0.06), (s * 1.0, y - 0.1, z + 0.02), dark, parent=hull, rot=(SLOPE, 0, 0))
        # Headlight clusters in their guards at the glacis foot corners, tow hooks below.
        y, z = _on_glacis(0.14, 0.065)
        box("light", (0.16, 0.1, 0.12), (s * 1.08, y, z), dark, parent=hull)
        box("light_glass", (0.1, 0.02, 0.07), (s * 1.08, y + 0.06, z), glass, parent=hull)
        box("light_guard", (0.24, 0.14, 0.03), (s * 1.08, y + 0.02, z + 0.1), paint, parent=hull)
        box("tow_hook", (0.1, 0.16, 0.12), (s * 0.7, 2.05, 0.82), dark, parent=hull)
    # Driver's hatch (front left) with its periscopes, engine louvres (front right), exhaust on the right.
    cyl("driver_hatch", 0.3, 0.05, (-0.72, 0.62, ROOF + 0.025), paint, segments=16, parent=hull)
    for k in range(4):
        ang = math.radians(-50 + k * 33)
        box("periscope", (0.12, 0.06, 0.07), (-0.72 + 0.36 * math.sin(ang), 0.62 + 0.36 * math.cos(ang),
                                              ROOF + 0.04), glass, parent=hull, rot=(0, 0, -math.degrees(ang)))
    box("louvre_frame", (0.85, 0.6, 0.04), (0.55, 0.62, ROOF + 0.02), paint, parent=hull)
    for k in range(6):
        box("louvre", (0.78, 0.04, 0.03), (0.55, 0.4 + k * 0.088, ROOF + 0.05), dark, parent=hull)
    box("exhaust_box", (0.1, 0.5, 0.36), (HULL_W / 2 + 0.05, 1.05, 1.45), dark, parent=hull)
    box("exhaust_grille", (0.11, 0.42, 0.04), (HULL_W / 2 + 0.06, 1.05, 1.66), paint, parent=hull)
    # Cargo hatch over the troop compartment, hinged at the rear.
    hatch = box("cargo_hatch", (1.3, 1.25, 0.05), (0, -1.45, ROOF + 0.025), paint, parent=hull, bevel=0.01)
    for s in (-1, 1):
        box("hinge", (0.12, 0.1, 0.06), (s * 0.45, -2.1, ROOF + 0.03), dark, parent=hull)
        box("grab_rail", (0.04, 0.9, 0.04), (s * 1.18, -0.8, ROOF + 0.04), dark, parent=hull)
        cyl("antenna_base", 0.05, 0.12, (s * 1.05, -1.95, ROOF + 0.06), dark, segments=8, parent=hull)
        cyl("antenna", 0.008, 2.0, (s * 1.05, -1.95, ROOF + 1.1), dark, segments=4, parent=hull)
    # Rear: ramp in the rear plate with its door, the A3's two armoured fuel tanks either side.
    box("ramp", (1.4, 0.05, 1.25), (0, REAR - 0.02, 1.13), paint, parent=hull, bevel=0.01)
    box("ramp_door", (0.55, 0.03, 0.95), (-0.25, REAR - 0.055, 1.18), paint, parent=hull)
    box("door_handle", (0.12, 0.04, 0.04), (0.0, REAR - 0.08, 1.2), dark, parent=hull)
    lens = mat("lens", (0.5, 0.08, 0.05))
    for s in (-1, 1):
        box("fuel_tank", (0.42, 0.23, 1.0), (s * 1.0, REAR - 0.115, 1.08), paint, parent=hull, bevel=0.03)
        box("tank_strap", (0.44, 0.24, 0.05), (s * 1.0, REAR - 0.115, 1.35), dark, parent=hull)
        box("tank_strap", (0.44, 0.24, 0.05), (s * 1.0, REAR - 0.115, 0.8), dark, parent=hull)
        box("tail_light", (0.1, 0.04, 0.08), (s * 1.0, REAR - 0.24, 1.66), lens, parent=hull)
    # Side: the top-run lip over the tracks and a line of armour bolts.
    for s in (-1, 1):
        box("side_lip", (0.08, 4.1, 0.04), (s * (HULL_W / 2 - 0.02), -0.15, 0.95), dark, parent=hull)
        for k in range(7):
            box("bolt", (0.02, 0.04, 0.04), (s * (HULL_W / 2 + 0.005), 0.8 - k * 0.45, 1.75), dark, parent=hull)
    return hull, hatch


def _running_gear(hull, paint, rubber, steel):
    top = 0.92
    for s in (-1, 1):
        x = s * TRACK_X
        for y in ROAD_Y:
            for dx in (-0.095, 0.095):
                cyl("roadwheel", WHEEL_R - 0.04, 0.1, (x + dx, y, WHEEL_Z), paint, axis="X", segments=16,
                    parent=hull)
                cyl("tyre", WHEEL_R, 0.08, (x + dx, y, WHEEL_Z), rubber, axis="X", segments=16, parent=hull)
            cyl("hub", 0.08, TRACK_W + 0.02, (x, y, WHEEL_Z), paint, axis="X", segments=8, parent=hull)
            box("arm", (0.06, 0.35, 0.08), (s * (LOWER_W / 2 + 0.03), y + 0.15, WHEEL_Z + 0.1), steel,
                parent=hull, rot=(-25, 0, 0))
        sy, sz, sr = SPROCKET
        cyl("sprocket", sr, 0.3, (x, sy, sz), paint, axis="X", segments=12, parent=hull, bevel=0.02)
        cyl("sprocket_teeth", sr + 0.04, 0.1, (x, sy, sz), steel, axis="X", segments=12, parent=hull)
        iy, iz, ir = IDLER
        cyl("idler", ir, 0.32, (x, iy, iz), paint, axis="X", segments=16, parent=hull, bevel=0.02)
        # The belt: its tread scrolls in the engine (material "track", convert.track_belts).
        _usveh.track_loop("belt", x, TRACK_W, SPROCKET, IDLER, top, (ROAD_Y[0] + 0.3, ROAD_Y[-1] - 0.3),
                          TRACK_T, hull)


def _cupola(hull, paint, dark, glass):
    turret = cyl("turret", 0.45, 0.14, RING, paint, segments=20, parent=hull, bevel=0.02)
    cyl("cupola_top", 0.38, 0.06, (0, 0, 0.1), paint, segments=20, parent=turret)
    for k in range(5):
        ang = math.radians(-150 + k * 60)
        box("vision_block", (0.14, 0.06, 0.08), (0.4 * math.sin(ang), 0.4 * math.cos(ang), 0.06), glass,
            parent=turret, rot=(0, 0, -math.degrees(ang)))
    # Hatch standing open to the rear.
    box("cupola_hatch", (0.58, 0.05, 0.5), (0, -0.4, 0.38), paint, parent=turret, rot=(-12, 0, 0), bevel=0.01)
    # Gun shield: a front plate with a slot for the gun, angled wings and side plates.
    box("shield", (0.32, 0.03, 0.5), (0, 0.48, 0.42), paint, parent=turret)
    box("shield_top", (0.26, 0.03, 0.08), (0, 0.48, 0.64), paint, parent=turret)
    for s in (-1, 1):
        box("shield_wing", (0.36, 0.03, 0.5), (s * 0.3, 0.42, 0.42), paint, parent=turret, rot=(0, 0, -s * 25))
        box("shield_side", (0.03, 0.4, 0.4), (s * 0.48, 0.18, 0.38), paint, parent=turret)
    cyl("pintle", 0.03, 0.4, (0, 0.28, 0.25), dark, segments=8, parent=turret)
    box("cradle", (0.12, 0.2, 0.06), (0, 0.3, 0.46), dark, parent=turret)
    _usveh.m2_50cal("m2", turret, (0, 0.32, 0.55))
    return turret


def build(wreck=False):
    paint = mat("m113_green", (0.33, 0.36, 0.24))
    dark = mat("dark_metal", (0.1, 0.1, 0.09))
    glass = mat("glass", (0.05, 0.07, 0.08))
    rubber = mat("rubber", (0.07, 0.07, 0.065))
    steel = mat("running_steel", (0.16, 0.15, 0.14))
    hull, hatch = _hull(paint, dark, glass)
    _running_gear(hull, paint, rubber, steel)
    turret = _cupola(hull, paint, dark, glass)
    if wreck:
        turret.location.z += 0.1
        turret.location.y -= 0.15
        turret.rotation_euler = (0.25, -0.18, 1.2)
        # The cargo hatch blown off its hinges, lying askew on the roof.
        hatch.location = (0.3, -1.3, ROOF + 0.15)
        hatch.rotation_euler = (0.25, 0.12, 0.5)
    return _usveh.done(hull)


FINISH = {"keep": ("hull", "turret")}
PREVIEW = {"distance": 10}
