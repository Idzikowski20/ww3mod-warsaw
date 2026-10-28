"""WOOD segment: a picket fence from y = 0 to 4 (one cell at Scale 2): two rails and pointed palings every
13 cm, 1.4 m high, a few weathered darker or missing. Hand-built."""

import random
import _defences as D
from lib import box, prism, mat


def build(wreck=False):
    random.seed(5)
    wood = mat("wood", D.WOOD)
    old = mat("wood_old", (0.28, 0.22, 0.15))
    o = D.root(box("hull", (0.05, 4.0, 0.1), (0.06, 2.0, 0.35), wood))
    box("rail", (0.05, 4.0, 0.1), (0.06, 2.0, 1.1), wood, parent=o)
    for i in range(28):
        if random.random() < 0.06:
            continue  # a missing paling
        y = 0.14 + i * 0.1335
        h = 1.4 + random.uniform(-0.04, 0.04)
        prism("paling", [(-0.04, 0.05), (0.04, 0.05), (0.04, h - 0.08), (0.0, h), (-0.04, h - 0.08)], 0.025,
              (0.1, y, 0), old if random.random() < 0.25 else wood, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 7, "target_z": 0.7}
