"""M2A3 Bradley from "M2 Bradley IFV" by 42manako (CC-BY-4.0,
sketchfab.com/3d-models/m2-bradley-ifv-ab022158ab5f4fbfa55d4142db7595ab).
Real length 6.55 m. The turret is its own object in the source; the 25 mm M242 is cut out of it by position."""

import convert
import _usveh

SOURCE = "bradley_ifv.glb"
LENGTH = 6.55
RING = (0.15, -0.4, 2.02)     # turret ring centre (model metres, after normalize)
GUN = (0.12, 0.75, 2.52)      # M242 trunnion; the gun axis runs along +Y at this x/z


def build(wreck=False):
    o = _usveh.load(SOURCE, group=lambda n, lo, hi: "turret" if n.startswith("turret") else "hull")
    convert.raw_colours(o)
    # The source paint is near black; the game's Bradley (cameo) is desert tan like the Abrams.
    _usveh.paint(o, _usveh.TAN, gain=9.0, only={"Image_2"})
    convert.normalize(o, front="-Y", length=LENGTH)
    convert.weld(o)
    parts = _usveh.split(o, {
        "barrel": lambda c, g: g == "turret" and abs(c.x - GUN[0]) < 0.09 and abs(c.z - GUN[2]) < 0.09
                               and c.y > GUN[1] + 0.1,
        "turret": lambda c, g: g == "turret",
    }, rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    if wreck:
        turret.location += convert.Vector((0.1, -0.15, 0.22))
        turret.rotation_euler = (-0.12, 0.16, -0.75)
        barrel.rotation_euler = (-0.25, 0, 0)
    return _usveh.done(hull)


FINISH = {"flat": False}
