"""FENC post: a wire-fence post, hand-built - a 2 m creosoted timber post (14 cm) with a cap and a cap. At the origin; segments run along +y."""

import _defences as D
from lib import box, cyl, mat


def build(wreck=False):
    wood = mat("creosote", (0.22, 0.17, 0.11))
    o = D.root(cyl("hull", 0.07, 2.0, (0, 0, 1.0), wood, segments=8))
    cyl("cap", 0.08, 0.06, (0, 0, 2.02), wood, segments=8, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 6, "target_z": 1.0}
