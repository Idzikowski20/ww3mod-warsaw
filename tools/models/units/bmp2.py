"""BMP-2 from "BMP-2" by 42manako (CC-BY-4.0, sketchfab.com/3d-models/bmp-2-a843e922897c499ca53e718235b3875a).
Real length 6.735 m. The source ships the turret (and its Konkurs launcher) as their own materials; the
30 mm 2A42 gun is cut out of the turret by position. 113k triangles: each part is decimated on its own."""

import convert
import _ruv

SOURCE = "bmp-2.glb"
LENGTH = 6.735
RING = (0.0, -0.83, 1.70)   # turret ring centre (measured on the normalized model)
GUN = (-0.04, 0.0, 2.0)     # gun trunnion in the mantlet


def build(wreck=False):
    o = _ruv.load(SOURCE, "-X", LENGTH)
    convert.recolor(o, _ruv.RU_GREEN, 0.9)      # the source wears a desert camouflage
    parts = _ruv.split(o, {
        "barrel": lambda c, m: m.startswith("Base") and abs(c.x - GUN[0]) < 0.1 and abs(c.z - GUN[2]) < 0.1
        and c.y > GUN[1] + 0.15,
        "turret": lambda c, m: m.startswith(("Base", "Kornet")),
    })
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.decimate(hull, 17000)
    convert.decimate(turret, 6500)
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)


    if wreck:
        _ruv.turret_off(turret, barrel, lift=0.15, rot=(-0.1, 0.12, -0.5), droop=-0.12)
        _ruv.tilt(hull, roll=-0.04, pitch=0.03, sink=0.05)
    return _ruv.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 11}
