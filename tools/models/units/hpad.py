"""HPAD: helipad - the helicopter pad cut out of "Airport" by nermin (CC-BY-4.0,
sketchfab.com/3d-models/airport-734cef12f0a045df93fc8aa41401a123): its marked bay with the H and the dashed
safety border, scaled so the H is a real 6 m (1 unit = 3.5 cm), a 13.9 m square, on a concrete slab. Added by
hand: edge lights, a windsock mast, a refuelling point with a hose reel,
fuel drums and sandbags. The helipad's centre is half a cell north of its 2 x 2 footprint's middle
(LocalCenterOffset 0,-512,0), so the model is shifted half a cell south."""

import math
import convert
import _defences as D
from lib import box, cyl, mat

SOURCE = "airport_ladowisko.glb"
K = 0.035
SIZE = 396 * K                  # 13.9 m
SOUTH = -4.0 / 1.15             # half a cell (4 m in game) at Scale 1.15, in model metres
SLAB = 0.15


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    D.crop(o, (156, -487, -1.0), (552, -91, 5.0))
    p = D.fit(o, k=K, centre=(354, -289, 0), lift=SLAB)
    o.data.transform(__import__("mathutils").Matrix.Translation((0, SOUTH, 0)))
    steel = mat("steel", D.STEEL)
    yellow = mat("lamp", (0.85, 0.7, 0.2))
    D.pad("slab", (SIZE + 0.6, SIZE + 0.6), (0, SOUTH, 0), height=SLAB, parent=o)
    h = SIZE / 2 + 0.15
    for i in range(12):  # edge lights round the pad
        a = i / 12 * 4
        side, t = int(a), (a % 1) * 2 - 1
        x, y = [(t * h, -h), (h, t * h), (-t * h, h), (-h, -t * h)][side]
        cyl("edge_light", 0.08, 0.3, (x, y + SOUTH, SLAB + 0.15), yellow, segments=6, parent=o)

    # Windsock mast at the north-west corner.
    mx, my = -h - 0.9, h - 1.0 + SOUTH
    if wreck:
        cyl("mast", 0.07, 5.0, (mx + 2.3, my, 0.25), steel, axis="X", segments=6, parent=o)
    else:
        cyl("mast", 0.07, 5.0, (mx, my, 2.5), steel, segments=6, parent=o)
        cyl("windsock", 0.32, 1.6, (mx + 0.85, my, 4.75), mat("sock", (0.85, 0.4, 0.1)), axis="X", segments=8, radius2=0.18, parent=o)
    # Refuelling point east of the pad: hose reel cart, drums, a sandbag wall.
    fx, fy = h + 1.3, -3.0 + SOUTH
    box("reel_cart", (1.0, 1.4, 0.8), (fx, fy, 0.4), mat("olive", D.OLIVE), parent=o, bevel=0.03)
    cyl("reel", 0.38, 0.6, (fx, fy, 0.95), mat("black", D.BLACK), axis="X", segments=12, parent=o)
    for i in range(4):
        cyl("drum", 0.29, 0.88, (fx - 0.3 + (i % 2) * 0.62, fy + 1.4 + (i // 2) * 0.62, 0.44),
            mat("drum", (0.22, 0.3, 0.2)), segments=10, parent=o)
    D.sandbag_row((fx + 1.0, fy - 1.2, 0), (fx + 1.0, fy + 2.6, 0), layers=1, parent=o)
    if wreck:
        D.shard_scatter(12, (-h, -h + SOUTH, h, h + SOUTH), z=SLAB, parent=o)
    return D.done(o)


FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 26, "target_z": 0.0}
