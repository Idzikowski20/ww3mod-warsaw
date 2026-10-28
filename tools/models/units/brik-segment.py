"""BRIK segment: 4 m of the panel of "Concrete_wall_Protection" by Mehdi Shahsavan (CC-BY-4.0,
sketchfab.com/3d-models/concrete-wall-protection-47c3c48fac3a4f0c8ca0fe61d34daff2): a cast panel 4 m tall,
running y = 0..4 (one cell at Scale 2) from the post at the origin, a razor-wire coil along its top (the
source's 230k-triangle wire, rebuilt as rings)."""

import _defences as D


def build(wreck=False):
    o = D.wall_piece(-4.5, -0.5)
    D.concertina(0.0, D.CELL, 4.25, 0.3, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 12, "target_z": 2.0}
