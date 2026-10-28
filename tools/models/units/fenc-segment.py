"""FENC segment: four strands of barbed wire from the post at y = 0 to the next at y = 4 (one cell at
Scale 2), with a thinner timber stake halfway. Hand-built."""

import _defences as D
from lib import box, cyl, mat


def build(wreck=False):
    wire = mat("wire", (0.2, 0.2, 0.19))
    wood = mat("creosote", (0.22, 0.17, 0.11))
    o = D.root(cyl("hull", 0.05, 1.8, (0, 2.0, 0.9), wood, segments=6))
    for z in (0.45, 0.85, 1.25, 1.65):
        box("strand", (0.025, 4.0, 0.025), (0.06, 2.0, z), wire, parent=o)
        for i in range(8):  # barbs
            box("barb", (0.06, 0.02, 0.06), (0.06, 0.25 + i * 0.5, z), wire, parent=o, rot=(0, 45, 0))
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 7, "target_z": 0.8}
