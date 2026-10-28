"""BARB segment: a concertina of barbed wire 0.9 m across from y = 0 to 4 (one cell at Scale 2), pinned by
two screw pickets with a strand along the top. Hand-built (rings stand for the stretched coil)."""

import _defences as D
from lib import box, mat


def build(wreck=False):
    steel = mat("picket", (0.24, 0.23, 0.2))
    o = D.root(box("hull", (0.05, 0.05, 1.1), (0.0, 1.3, 0.55), steel, rot=(0, 0, 45)))
    box("picket", (0.05, 0.05, 1.1), (0.0, 2.7, 0.55), steel, parent=o, rot=(0, 0, 45))
    D.concertina(0.0, 4.0, 0.45, 0.45, parent=o, pitch=0.2)
    box("top_strand", (0.02, 4.0, 0.02), (0, 2.0, 0.92), mat("wire", (0.2, 0.2, 0.19)), parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 7, "target_z": 0.5}
