"""TOS-1A Solntsepyok heavy flamethrower system: the T-72 chassis with a 24-tube 220 mm launcher.

The chassis is the hull of "T90" by Karnage (CC-BY-4.0, sketchfab.com/3d-models/t90-8f577602505248f79e2b8a95f24b33fb),
the T-72's direct descendant, with its turret and gun cut away; the launcher is built here.
Not used: "TOS-1A.glb" in the sources is really "Type 75 MLRS (War Thunder)" by KojfDiscord, a Japanese
130 mm launcher on an aluminium APC hull, nothing like the TOS.

Real length 9.5 m, height 3.1 m. The launcher, on its turntable, is the turret."""

import bpy
from mathutils import Matrix, Vector

import convert
import t90
import _ruv
from lib import box, cyl, mat, prism

GREEN = (0.36, 0.39, 0.29)   # matches the chassis paint
ROWS, COLS = 3, 8           # 24 tubes
TUBE = 0.24                 # tube outer diameter, m (220 mm rockets)


def _chassis():
    o = _ruv.load(t90.SOURCE, "-Y", t90.LENGTH)
    ring = Vector(t90.RING)
    r2 = (1.25 * t90.K) ** 2
    parts = _ruv.split(o, {
        "gone": lambda c, m: c.z > ring.z + 0.02 and ((c.x - ring.x) ** 2 + (c.y - ring.y) ** 2 < r2
                                                      or (abs(c.x - t90.GUN_X) < 0.25 and c.y > ring.y)),
    })
    bpy.data.objects.remove(parts["gone"], do_unlink=True)
    hull = parts["hull"]
    lo, hi = convert.bounds(hull)
    shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, 0))
    hull.data.transform(Matrix.Translation(shift))
    return hull, ring + shift


def _launcher(turret, wreck):
    """The launch module, in the turret's space (origin on the turntable centre, front +Y)."""
    green = mat("tos_green", GREEN)
    dark = mat("tos_tube", (0.07, 0.07, 0.06))
    steel = mat("tos_steel", (0.22, 0.22, 0.2))
    # Turntable and the cradle that carries the module on its trunnions.
    cyl("table", 1.5, 0.22, (0, 0, 0.11), green, segments=24, parent=turret, bevel=0.03)
    box("cradle", (1.9, 1.6, 0.35), (0, -0.4, 0.38), green, parent=turret, bevel=0.03)
    for side in (-1, 1):
        prism("trunnion", [(-1.2, 0.2), (0.3, 0.2), (0.1, 0.75), (-0.9, 0.75)], 0.12,
              (side * 0.98, 0, 0), green, parent=turret)
        cyl("pin", 0.12, 0.2, (side * 1.08, -0.6, 0.6), steel, axis="X", parent=turret)
    # Elevating jack under the front of the module.
    cyl("jack", 0.09, 0.7, (0, 0.95, 0.55), steel, parent=turret, rot=None) if False else \
        cyl("jack", 0.09, 0.7, (0, 0.95, 0.55), steel, parent=turret)

    # The armoured box: 24 tubes behind flat plates, open at both ends.
    w, h, length = COLS * TUBE + 0.22, ROWS * TUBE + 0.2, 4.9
    y0, z0 = 0.15, 0.75 + h / 2            # box centre
    box_ = box("box", (w, length, h), (0, y0, z0), green, parent=turret, bevel=0.02)
    # A ribbed lid and armour ribs along the flanks.
    box("lid", (w - 0.12, length - 0.3, 0.06), (0, y0, z0 + h / 2 + 0.03), green, parent=turret)
    for i in range(7):
        y = y0 - length / 2 + 0.45 + i * (length - 0.9) / 6
        for side in (-1, 1):
            box("rib", (0.05, 0.08, h + 0.04), (side * (w / 2 + 0.02), y, z0), green, parent=turret)
        box("rib", (w - 0.1, 0.08, 0.05), (0, y, z0 + h / 2 + 0.075), green, parent=turret)
    # Tube mouths at both ends, recessed a little into the box.
    for end in (-1, 1):
        face = y0 + end * (length / 2 + 0.005)
        box("face", (w - 0.08, 0.02, h - 0.08), (0, face, z0), steel, parent=turret)
        for r in range(ROWS):
            for c in range(COLS):
                x = (c - (COLS - 1) / 2) * TUBE
                z = z0 + (r - (ROWS - 1) / 2) * TUBE
                cyl("tube", TUBE / 2 - 0.015, 0.06, (x, face + end * 0.02, z), steel, axis="Y",
                    segments=10, parent=turret)
                cyl("bore", TUBE / 2 - 0.04, 0.062, (x, face + end * 0.025, z), dark, axis="Y",
                    segments=10, parent=turret)
    # Fire-control sight housing on the right front of the cradle, and a stowage box on the left.
    box("sight", (0.45, 0.55, 0.4), (w / 2 + 0.3, 0.9, 0.55), green, parent=turret, bevel=0.03)
    box("sight_glass", (0.3, 0.02, 0.14), (w / 2 + 0.3, 1.18, 0.62), dark, parent=turret)
    box("stowage", (0.4, 1.0, 0.35), (-w / 2 - 0.25, -0.6, 0.5), green, parent=turret, bevel=0.03)
    return box_


def build(wreck=False):
    hull, ring = _chassis()
    turret = box("turret", (0.01, 0.01, 0.01), ring, mat("tos_green", GREEN), parent=hull)
    _launcher(turret, wreck)

    if wreck:
        _ruv.turret_off(turret, lift=0.1, rot=(0.12, -0.15, 0.55))
        _ruv.tilt(hull, roll=0.03, pitch=-0.02, sink=0.05)
    return _ruv.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 14}
