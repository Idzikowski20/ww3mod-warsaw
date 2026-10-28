"""BTR-82A (the game's BTR-80 APC) from "Syrian BTR-82A" by 42manako (CC-BY-4.0,
sketchfab.com/3d-models/syrian-btr-82a-f8643495950446e69ce9ef62e0b2b256).
Real length 7.65 m. The source ships the turret as its own material; the 30 mm gun is cut out of it by position."""

import convert
import _ruv

SOURCE = "syrian_btr-82a.glb"
LENGTH = 7.65
RING = (0.0, 0.73, 2.0)     # turret ring centre (measured on the normalized model)
GUN = (0.04, 1.2, 2.58)     # gun trunnion in the mantlet
AXLES = (2.14, 0.67, -1.05, -2.40)   # wheel hubs along y; hub height 0.615, radius 0.62


def build(wreck=False):
    o = _ruv.load(SOURCE, "+X", LENGTH, tris=24000)
    convert.recolor(o, _ruv.RU_GREEN, 0.9)      # the source wears a desert camouflage
    parts = _ruv.split(o, {
        "barrel": lambda c, m: m.startswith("Turret") and abs(c.x - GUN[0]) < 0.09 and abs(c.z - GUN[2]) < 0.09
        and c.y > 1.52,
        "turret": lambda c, m: m.startswith("Turret"),
    })
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)
    if not wreck:
        _ruv.wheels(hull, AXLES, 0.615, 0.64, 0.9, "RrWheel", hub_x=1.21)


    if wreck:
        _ruv.turret_off(turret, barrel, lift=0.1, rot=(0.08, -0.12, 0.7), droop=-0.1)
        _ruv.tilt(hull, roll=0.05, pitch=-0.02, sink=0.08)
    return _ruv.done(hull)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES), "turret", "barrel"),
          "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 12}
