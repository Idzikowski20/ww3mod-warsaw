"""VGATE: the HGATE gate turned to run along y across 3 cells (12 m of model at Scale 2). Concrete from
"Concrete_wall_Protection" by Mehdi Shahsavan (CC-BY-4.0,
sketchfab.com/3d-models/concrete-wall-protection-47c3c48fac3a4f0c8ca0fe61d34daff2); leaves hand-built."""

import _defences as D


def build(wreck=False):
    return D.gate(turn=90)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 16, "target_z": 1.5}
