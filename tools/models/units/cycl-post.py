"""CYCL post: a chain-link fence post, hand-built - galvanised steel tube 2.4 m with a dome cap and the
45-degree extension arm for the barbed strands."""

import _defences as D
from lib import box, cyl, mat

GALV = (0.52, 0.53, 0.52)


def build(wreck=False):
    steel = mat("galvanised", GALV)
    o = D.root(cyl("hull", 0.05, 2.4, (0, 0, 1.2), steel, segments=8))
    cyl("cap", 0.065, 0.06, (0, 0, 2.42), steel, segments=8, parent=o)
    box("arm", (0.05, 0.05, 0.6), (0.2, 0, 2.6), steel, parent=o, rot=(0, 45, 0))
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 6, "target_z": 1.3}
