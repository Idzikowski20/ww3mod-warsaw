"""M270 MLRS from "Free M270" by Mr. Penguin (CC-BY-4.0, sketchfab.com/3d-models/free-m270-fc879301999a4cd0a09721b51affba9b).
Real length 6.86 m. The source shows the launcher loader module traversed 90 degrees to the left and
elevated; it is cut out by position and turned to face forward (still elevated, as when firing), and
is the turret node. The source running gear (half a million triangles of track links and wheels, which
no decimation keeps round) is replaced by a hand-built one at the same stations; its track belts carry the
scrolling track texture (convert.track_belts; tools/models/wiring/tracks-credits.md)."""

import convert
import _usveh
from lib import cyl, mat

SOURCE = "free_m270.glb"
K = 6.86 / 21.2                   # source hull length (Cube_0 and the track ends) -> real 6.86 m
RING = (0.0, -2.0, 1.36)          # launcher turntable centre on the deck (source 0.1, -6.52)
DECK = 1.38
CAB_REAR = 0.3
TRACK_X, TRACK_W = 1.456, 0.6     # track centre line and width (source x 3.48..5.52)
ROAD_Y = (2.037, 1.357, 0.286, -0.396, -1.409, -2.089)
WHEEL_R, WHEEL_Z = 0.324, 0.394
SPROCKET = (2.836, 0.688, 0.353)  # y, z, r (front drive)
IDLER = (-2.794, 0.717, 0.33)
ROLLERS = (1.75, 0.35, -1.75)
TRACK_T = 0.07
PAINT = (0.33, 0.36, 0.24)       # CARC green, a shade up: the flat colours have no texture highlights


def _source_part(n, lo, hi):
    if lo.x < -10:                # a loose rocket and a spare pod stand beside the vehicle
        return False
    # running gear: whole objects inside a track zone, below the fender
    return not ((lo.x > 3.4 or hi.x < -3.4) and hi.z < 3.45)


def _running_gear(hull):
    rubber = mat("rubber", (0.07, 0.07, 0.065))
    green = mat("m270_green", PAINT)
    steel = mat("running_steel", (0.16, 0.15, 0.14))
    top = WHEEL_Z + WHEEL_R + 0.13
    for s in (-1, 1):
        x = s * TRACK_X
        for y in ROAD_Y:
            for dx in (-0.16, 0.16):
                cyl("roadwheel", WHEEL_R, 0.13, (x + dx, y, WHEEL_Z), green, axis="X", segments=16, parent=hull)
                cyl("tyre", WHEEL_R + 0.012, 0.11, (x + dx, y, WHEEL_Z), rubber, axis="X", segments=16, parent=hull)
            cyl("hub", 0.09, TRACK_W + 0.04, (x, y, WHEEL_Z), green, axis="X", segments=8, parent=hull)
        sy, sz, sr = SPROCKET
        cyl("sprocket", sr, 0.36, (x, sy, sz), green, axis="X", segments=12, parent=hull, bevel=0.03)
        cyl("sprocket_teeth", sr + 0.04, 0.14, (x, sy, sz), steel, axis="X", segments=12, parent=hull)
        iy, iz, ir = IDLER
        cyl("idler", ir, 0.4, (x, iy, iz), green, axis="X", segments=16, parent=hull, bevel=0.03)
        for y in ROLLERS:
            cyl("roller", 0.11, 0.3, (x, y, top - 0.11 - TRACK_T), green, axis="X", segments=10, parent=hull)
        # The belt round sprocket, road wheels and idler; its tread scrolls in the engine (material "track").
        _usveh.track_loop("belt", x, TRACK_W, SPROCKET, IDLER, top, (ROAD_Y[0] + 0.2, ROAD_Y[-1] - 0.2),
                          TRACK_T, hull)


def build(wreck=False):
    o = _usveh.load(SOURCE, keep=_source_part)
    _usveh.recolor_flat(o, {"Material.001": PAINT, "Material.005": (0.22, 0.26, 0.17),
                            "Black": (0.07, 0.07, 0.065), "Black.001": (0.07, 0.07, 0.065),
                            "Material.004": (0.07, 0.07, 0.065), "iron": (0.12, 0.12, 0.11)})
    # Front is already +Y. Centre on the vehicle (source x = 0, hull y centre -0.375), ground at the
    # source track bottom (z -0.07), real size.
    o.data.transform(convert.Matrix.Scale(K, 4) @ convert.Matrix.Translation((0, 0.375, 0.07)))
    convert.weld(o)
    parts = convert.split(o, {"turret": lambda c: c.z > DECK and c.y < CAB_REAR}, rest="hull")
    hull, turret = parts["hull"], parts["turret"]
    _usveh.turn(turret, -90, RING)
    convert.decimate(hull, 12500)
    convert.decimate(turret, 8000)
    convert.pivot(turret, RING)
    convert.parent(turret, hull)
    _running_gear(hull)

    if wreck:
        turret.rotation_euler = (0.1, -0.12, 0.6)
    return _usveh.done(hull)


FINISH = {"flat": False}
