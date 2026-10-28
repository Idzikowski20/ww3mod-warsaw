"""AGUN: ZU-23-2 twin 23 mm anti-aircraft gun, from "ZU-23" by LuckySkink9661 (CC-BY-4.0,
sketchfab.com/3d-models/zu-23-23-fdae5a37901941fea3a02578506072a3). Real size: 4.57 m long with the barrels,
2.88 m wide; the source (5.55 m, barrels along +X) is scaled to that. The upper carriage (cradle, barrels,
seats, sights, ammunition boxes) is the turret, turning over the platform's pivot; the lower carriage with its
wheels and jacks stays. It sits in a ring of sandbags, as ZU-23s are dug in at checkpoints."""

import math
import convert
import _defences as D
from lib import box, mat

SOURCE = "zu-23.glb"
K = 4.57 / 5.55
PIVOT = (0.0, 0.0, 0.45)  # source: centre of the traversing platform, its top
TRUNNION = (0.1, 0.0, 1.08)  # source: the cradle's elevation axis, on the barrels' line


def _barrels(s):
    return s.x > 0.4 and abs(s.y) < 0.35 and s.z > 0.8


def _turret(s):
    if abs(s.y) > 0.85 and s.z < 0.62:                         # the wheels stay
        return False
    return s.z > 0.5 and (s.x - PIVOT[0]) ** 2 + s.y ** 2 < 1.45 ** 2


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.decimate(o, 7500)  # + 8 sandbag piles (900 each): under the 15k defence budget
    convert.raw_colours(o)
    p = D.fit(o, rot=90, k=K, centre=(PIVOT[0], 0, 0))
    parts = convert.split(o, {"barrel": lambda c: _barrels(p.src(c)), "turret": lambda c: _turret(p.src(c))},
                          rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, p(*PIVOT))
    convert.pivot(barrel, p(*TRUNNION))
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    # Emplacement: a ring of sandbags (one pile high, so the barrels clear it), open at the back.
    ring = []
    for i in range(8):
        a = math.radians(-105 + i * 30)  # from the right-rear round the front to the left-rear
        r = 2.25
        ring.append(D.prop("sandbag", (r * math.sin(a), r * math.cos(a), 0), rot=-math.degrees(a),
                           tilt=((8 if wreck and i % 3 == 0 else 0), 0), parent=hull))

    if wreck:
        turret.rotation_euler = (0.1, -0.22, 0.6)
        turret.location.z += 0.12
        barrel.rotation_euler = (-0.25, 0, 0)
        for o in ring[3:4]:  # a blown gap in the sandbags
            o.location.z -= 0.35
    return D.done(hull)


FINISH = {"flat": False, "keep": ("hull", "turret", "barrel")}
PREVIEW = {"distance": 10, "target_z": 0.7}
