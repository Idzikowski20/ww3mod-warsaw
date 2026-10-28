"""M109A6 Paladin from "M109A3 Paladin" by 42manako (CC-BY-4.0,
sketchfab.com/3d-models/m109a3-paladin-5747d6fbd28242e29b2cd8c9e668a516).
Real length with the gun forward: 9.12 m. One mesh: turret and the 155 mm tube are cut out by position."""

import convert
import _usveh

SOURCE = "m109a3_paladin.glb"
LENGTH = 9.12
RING = (0.0, -1.2, 1.52)      # turret ring centre (model metres, after normalize)
GUN = (0.0, -0.2, 1.81)       # trunnion; the tube runs along +Y at this x/z


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    _usveh.paint(o, _usveh.GREEN, gain=6.0, amount=0.7, only={"Image_0"})
    convert.normalize(o, front="+X", length=LENGTH)
    parts = convert.split(o, {
        "barrel": lambda c: abs(c.x - GUN[0]) < (0.3 if c.y > 4.0 else 0.22) and 1.66 < c.z < 2.05 and c.y > 0.3,   # not the travel lock below
        "turret": lambda c: c.z > 1.6 and c.y < 0.32 and abs(c.x) < 1.6,
    }, rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    if wreck:
        turret.location += convert.Vector((0.15, 0.1, 0.18))
        turret.rotation_euler = (0.08, 0.14, -0.45)
        barrel.rotation_euler = (-0.16, 0, 0)
    return _usveh.done(hull)


FINISH = {"flat": False}
