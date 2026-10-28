"""SAM: MIM-104 Patriot launching station (M901), from "MIM-104 Patriot Surface-To-Air Missile (SAM)" by
Muhamad Mirza Arrafi (CC-BY-4.0, sketchfab.com/3d-models/mim-104-patriot-surface-to-air-missile-sam-7a64d0af78514a159877edab1ab2bccb).
The source is the launcher hitched to its HEMTT tractor, 22.6 units long; scaled 0.77 to real size (HEMTT
tyres 1.2 m), the tractor and the semitrailer's gooseneck cut away, leaving the emplaced semitrailer (8.4 m)
on its four outrigger jacks, the outriggers drawn in to fit the site. The trailer lies along x (the site is
2 x 1 cells); the elevated four-canister launcher is the turret, turning about its own centre."""

import math
import convert
import _defences as D
from lib import box, mat
from mathutils import Matrix

SOURCE = "mim-104_patriot_surface-to-air_missile_sam.glb"
K = 0.77
CUT_X = -2.75             # source x: trailer ahead of this (gooseneck, generator, tractor) is cut away
PIVOT = (-8.8, 0.0, 2.7)  # source: under the launcher's centre, on the trailer deck
DECK_Z = 2.85             # source: launcher parts are above the deck


def _launcher(s):
    return s.z > DECK_Z and -13.6 < s.x < -3.9


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    D.crop(o, (None, None, None), (CUT_X, None, None))
    # Outriggers drawn in: what sticks out past the trailer's sides is pulled toward it.
    for v in o.data.vertices:
        if abs(v.co.y) > 2.7:
            v.co.y = math.copysign(2.7 + (abs(v.co.y) - 2.7) * 0.35, v.co.y)
    convert.decimate(o, 11000)
    p = D.fit(o, rot=0, k=K, centre=(-8.2, 0, 0))
    parts = convert.split(o, {"turret": lambda c: _launcher(p.src(c))}, rest="hull")
    hull, turret = parts["hull"], parts["turret"]
    convert.pivot(turret, p(*PIVOT))
    # The launcher fires toward the old tractor (+x); the engine's turret front is +y at rest.
    turret.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))
    convert.parent(turret, hull)

    if wreck:
        turret.rotation_euler = (-0.35, 0.18, 0.4)
        turret.location.z -= 0.3
    return D.done(hull)


FINISH = {"flat": False, "keep": ("hull", "turret")}
PREVIEW = {"distance": 18, "target_z": 2.0}
