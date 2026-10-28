"""2K22 Tunguska from "2K22 Tunguska" by usedm (CC-BY-4.0,
sketchfab.com/3d-models/2k22-tunguska-54ff4d655755473d99eab1ccc7eb6bfc).
Real length 7.93 m. The turret (guns, missiles, radars) is its own material in the source; it turns as one."""

import convert
import _ruv

SOURCE = "2k22_tunguska.glb"
LENGTH = 7.93
RING = (0.0, 0.8, 1.7)      # turret ring centre (measured on the normalized model)


def build(wreck=False):
    o = _ruv.load(SOURCE, "-Y", LENGTH, tris=24000)
    parts = _ruv.split(o, {
        # the turret material also holds the road-wheel dampers; the whip antenna on the turret roof is
        # in the hull material: everything standing above the hull roof turns with the turret.
        "turret": lambda c, m: (m == "Material_29" and c.z > 1.6) or (c.z > 1.9 and abs(c.y - RING[1]) < 2.8),
    })
    hull, turret = parts["hull"], parts["turret"]
    convert.pivot(turret, RING)
    convert.parent(turret, hull)


    if wreck:
        _ruv.turret_off(turret, lift=0.15, rot=(0.1, -0.12, 0.5))
        _ruv.tilt(hull, roll=0.04, pitch=-0.03, sink=0.06)
    return _ruv.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 13}
