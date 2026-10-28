"""BARB post: the anchor of a barbed-wire obstacle, hand-built - a steel screw picket (angle iron, 1.5 m)
with a coil end gathered on it and a marker rag."""

import _defences as D
from lib import box, mat


def build(wreck=False):
    steel = mat("picket", (0.24, 0.23, 0.2))
    o = D.root(box("hull", (0.06, 0.06, 1.5), (0, 0, 0.75), steel, rot=(0, 0, 45)))
    D.torus("coil_end", 0.42, 0.01, (0, 0, 0.45), rot=(0, 0, 90), seg=12, parent=o)
    D.torus("coil_end", 0.4, 0.01, (0, 0.08, 0.45), rot=(0, 0, 70), seg=12, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 6, "target_z": 0.6}
