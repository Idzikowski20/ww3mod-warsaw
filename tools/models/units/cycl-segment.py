"""CYCL segment: chain-link fence from y = 0 to 4 (one cell at Scale 2): top rail, bottom tension wire, the
diamond mesh 2.3 m high (drawn as its diagonal wires every 0.3 m), three barbed strands on the extension
arms. Hand-built."""

import math
import _defences as D
from lib import box, cyl, mat

GALV = (0.52, 0.53, 0.52)
H = 2.3


def build(wreck=False):
    steel = mat("galvanised", GALV)
    mesh = mat("mesh", (0.42, 0.43, 0.42))
    o = D.root(cyl("hull", 0.03, 4.0, (0, 2.0, H), steel, axis="Y", segments=6))  # top rail
    box("tension", (0.015, 4.0, 0.015), (0, 2.0, 0.08), steel, parent=o)
    step = 0.3
    for i in range(int((4.0 + H) / step) + 1):  # 45-degree mesh wires both ways, clipped to the panel
        y0 = -H + i * step  # where the rising wire leaves z = 0
        ya, yb = max(0.0, y0), min(4.0, y0 + H)
        if yb - ya < 0.05:
            continue
        za, zb = ya - y0, yb - y0
        ln = math.hypot(yb - ya, zb - za)
        for sign in (-1, 1):
            cy = (ya + yb) / 2 if sign > 0 else 4.0 - (ya + yb) / 2
            box("mesh", (0.012, ln, 0.012), (0.012 * sign, cy, (za + zb) / 2), mesh, parent=o,
                rot=(45 * sign, 0, 0))
    for k in range(3):
        box("barbed", (0.015, 4.0, 0.015), (0.12 + k * 0.13, 2.0, 2.45 + k * 0.13), steel, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": True, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 8, "target_z": 1.2}
