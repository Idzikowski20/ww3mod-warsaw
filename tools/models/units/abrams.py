"""M1A2 Abrams from "M1A1 Abrams Main Battle Tank" by Muhamad Mirza Arrafi (CC-BY-4.0,
sketchfab.com/3d-models/m1a1-abrams-main-battle-tank-1529f5d842cb4f578aa8cb672524f044).
The game unit is an M1A2; the M1A1 source (no CITV on the turret roof) stands in for it.
Real length with the gun forward: 9.77 m. One mesh: turret and gun are cut out by position."""

import convert
import _usveh

SOURCE = "m1a1_abrams.glb"
LENGTH = 9.77
RING = (0, -0.6, 1.62)      # turret ring centre (model metres, after normalize)
GUN = (0, 1.1, 2.08)       # gun trunnion


def _deck(y):
    """Hull roof height under the turret: flat, then rising behind the turret to the engine deck."""
    return 1.55 + min(max(-2.0 - y, 0.0), 1.2) * 0.217


def build(wreck=False):
    o = convert.load(SOURCE)  # its weld also merges the 30k faces the source carries twice
    convert.raw_colours(o)
    convert.normalize(o, front="-Y", length=LENGTH)
    # misc_a.4 is alpha-mapped decal cards. The ones on the turret cheeks bake to black squares; the ones on
    # the hull deck stay, the deck under them has no texture of its own.
    _usveh.drop_material(o, {"misc_a.4"}, where=lambda c: c.z > 1.85)
    parts = convert.split(o, {
        "barrel": lambda c: abs(c.x) < 0.2 and abs(c.z - GUN[2]) < 0.22 and c.y > GUN[1],
        "turret": lambda c: abs(c.x) < 1.8 and -4.5 < c.y < 1.75 and c.z > _deck(c.y) + 0.06,
    }, rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.decimate(hull, 13500)   # each part on its own, so no triangle spans the cut
    convert.decimate(turret, 9500)
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    if wreck:
        turret.location.z += 0.3
        turret.rotation_euler = (0.1, -0.18, 0.6)
        barrel.rotation_euler = (-0.2, 0, 0)
    return _usveh.done(hull)


FINISH = {"flat": False}
