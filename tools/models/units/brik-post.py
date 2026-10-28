"""BRIK post: the thick end pillar of "Concrete_wall_Protection" by Mehdi Shahsavan (CC-BY-4.0,
sketchfab.com/3d-models/concrete-wall-protection-47c3c48fac3a4f0c8ca0fe61d34daff2), 4 m tall, its razor
wire replaced by a hand-built coil. Stands at the origin; segments run along +y."""

import _defences as D
from lib import box
from mathutils import Matrix


def build(wreck=False):
    o = D.wall_piece(6.0, 7.28)
    lo, hi = D.convert.bounds(o)
    o.data.transform(Matrix.Translation((0, -(lo.y + hi.y) / 2, 0)))  # centred on the origin
    D.concertina(-0.4, 0.4, 4.25, 0.3, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 11, "target_z": 2.0}
