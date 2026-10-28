"""HGATE: a closed gate across 3 cells along x (12 m of model at Scale 2): two steel leaves between concrete
pillars, wall stubs to the footprint's ends. The concrete is cut from "Concrete_wall_Protection" by Mehdi
Shahsavan (CC-BY-4.0, sketchfab.com/3d-models/concrete-wall-protection-47c3c48fac3a4f0c8ca0fe61d34daff2);
the leaves and the coil are hand-built."""

import _defences as D


def build(wreck=False):
    return D.gate(turn=0)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 16, "target_z": 1.5}
