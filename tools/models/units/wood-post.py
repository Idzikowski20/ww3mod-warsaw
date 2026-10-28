"""WOOD post: a wooden fence post, hand-built - a 14 cm square sawn post 1.6 m high with a pyramid cap."""

import _defences as D
from lib import box, extrude, mat


def build(wreck=False):
    wood = mat("wood", D.WOOD)
    o = D.root(box("hull", (0.14, 0.14, 1.6), (0, 0, 0.8), wood))
    extrude("cap", [(-0.08, -0.08), (0.08, -0.08), (0.08, 0.08), (-0.08, 0.08)], 0.08, (0, 0, 1.6), wood,
            top_scale=0.1, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 5, "target_z": 0.8}
