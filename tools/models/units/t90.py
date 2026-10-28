"""T-90A from "T90" by Karnage (CC-BY-4.0, sketchfab.com/3d-models/t90-8f577602505248f79e2b8a95f24b33fb).
Real length with the gun forward: 9.63 m. The source is one mesh: turret and gun are cut out by position."""

import convert
from lib import box, mat

SOURCE = "t90_source.glb"
LENGTH = 9.63

# Measured in the source (front -Y, metres before scaling): bbox centre x 0.157 y 0.068, floor z 0.111,
# scale to real 1.355. Gun axis x 0.255 z 1.35; turret ring centre x 0.2 y 0.85, radius 1.25, base z 1.08.
K = 1.355


def _p(x, y, z):
    """Source point -> normalized model point (front turned to +Y, centred, on the ground, real size)."""
    return (-(x - 0.157) * K, -(y - 0.068) * K, (z - 0.111) * K)


RING = _p(0.2, 0.85, 1.08)
GUN = _p(0.255, -0.2, 1.35)
GUN_X, GUN_Z = GUN[0], GUN[2]


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.normalize(o, front="-Y", length=LENGTH)
    r2 = (1.25 * K) ** 2
    parts = convert.split(o, {
        "barrel": lambda c: abs(c.x - GUN_X) < 0.2 and abs(c.z - GUN_Z) < 0.2 and c.y > GUN[1] - 0.15,
        "turret": lambda c: c.z > RING[2] + 0.02 and (c.x - RING[0]) ** 2 + (c.y - RING[1]) ** 2 < r2,
    }, rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, RING)
    convert.pivot(barrel, GUN)
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    # Player colour: a recognition panel on the turret roof and stripes on the side skirts.
    team = mat("team", (0.9, 0.9, 0.9))
    box("roof_team", (0.8, 0.7, 0.03), (0.3, -0.9, 0.62), team, parent=turret)
    for side in (-1, 1):
        box("skirt_team", (0.05, 2.0, 0.16), (side * 1.9, -0.6, 1.22), team, parent=hull)

    if wreck:
        turret.location.z += 0.25
        turret.rotation_euler = (0.12, -0.2, 0.7)
        barrel.rotation_euler = (-0.18, 0, 0)
    return hull


FINISH = {"flat": False}
