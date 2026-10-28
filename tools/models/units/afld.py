"""AFLD: forward airfield - a stretch of paved strip with its threshold markings, edge lines and centreline,
cut from "Airport" by nermin (CC-BY-4.0, sketchfab.com/3d-models/airport-734cef12f0a045df93fc8aa41401a123),
scaled to fill the 3 x 2 cell site (16 x 10.7 m model, the strip 10.7 m wide), with sandbags from "Military/
Urban Prop Set" by Neslihan Çakmak (CC-BY-4.0, sketchfab.com/3d-models/militaryurban-prop-set-fc57f8223fbc4ec8a10e74cd43e735f1).
Hand-built: red-and-white edge marker posts and lights (the cameo's), an operations container with its
antenna and windsock, a fuel trailer and ammunition pallets for rearming. Wreck: cratered strip, burnt out."""

import math
import random
import convert
import _defences as D
from lib import box, cyl, mat

SOURCE = "airport_ladowisko.glb"
X0, X1, Y0, Y1 = 1216, 1930, 80, 553
K = 16.0 / (X1 - X0)
HX, HY = 8.0, (Y1 - Y0) * K / 2
SLAB = 0.12


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    D.crop(o, (X0, Y0, -1.0), (X1, Y1, 5.0))
    D.fit(o, k=K, centre=((X0 + X1) / 2, (Y0 + Y1) / 2, 0), lift=SLAB)
    D.pad("slab", (2 * HX + 0.3, 2 * HY + 0.3), height=SLAB, parent=o)
    white = mat("white", (0.8, 0.8, 0.78))
    red = mat("marker_red", (0.7, 0.12, 0.08))
    steel = mat("steel", D.STEEL)
    lamp = mat("lamp", (0.85, 0.7, 0.2))
    for side in (-1, 1):  # marker posts and edge lights along both edges
        for i in range(6):
            x = -7.2 + i * 2.9
            y = side * (HY - 0.25)
            for k in range(3):
                cyl("marker", 0.07, 0.3, (x, y, SLAB + 0.15 + k * 0.3), red if k % 2 == 0 else white, segments=6, parent=o)
            cyl("edge_light", 0.06, 0.2, (x + 1.45, y, SLAB + 0.1), lamp, segments=6, parent=o)

    # Operations container on the north edge, antenna and windsock beside it.
    D.container("ops", (-4.6, HY - 1.4, SLAB), rot=0, parent=o)
    cyl("antenna", 0.04, 5.5, (-7.4, HY - 0.6, SLAB + 2.59 + 2.75), steel, segments=6, parent=o)
    if not wreck:
        cyl("windsock_mast", 0.06, 4.0, (7.5, HY - 0.5, SLAB + 2.0), steel, segments=6, parent=o)
        cyl("windsock", 0.28, 1.4, (8.2, HY - 0.5, SLAB + 3.8), mat("sock", (0.85, 0.4, 0.1)), axis="X",
            segments=8, radius2=0.15, parent=o)
    # Fuel trailer and rearming pallets on the north-east of the strip.
    tank = mat("tank", (0.26, 0.29, 0.2))
    cyl("fuel_tank", 0.75, 3.4, (4.4, HY - 1.3, SLAB + 1.25), tank, axis="X", segments=14, parent=o, bevel=0.1)
    box("fuel_chassis", (3.8, 1.4, 0.25), (4.4, HY - 1.3, SLAB + 0.55), steel, parent=o)
    for x in (3.6, 5.2):
        for s in (-1, 1):
            cyl("fuel_wheel", 0.38, 0.25, (x, HY - 1.3 + s * 0.75, SLAB + 0.38), mat("black", D.BLACK), axis="Y",
                segments=10, parent=o)
    box("fuel_drawbar", (1.2, 0.12, 0.12), (2.1, HY - 1.3, SLAB + 0.55), steel, parent=o)
    for i in range(3):
        D.crates("ammo", (1.2 + i * 1.4, -HY + 1.1, SLAB), n=4 + 2 * i, parent=o, seed=i)
    D.sandbag_row((-7.6, -HY + 0.6, SLAB), (-3.6, -HY + 0.6, SLAB), layers=1, parent=o)

    if wreck:
        random.seed(3)
        black = mat("crater", (0.06, 0.055, 0.05))
        for i in range(4):  # bomb craters on the strip, scorched rings round them
            x, y = random.uniform(-6, 6), random.uniform(-3, 3)
            r = random.uniform(0.9, 1.5)
            cyl("crater", r, 0.04, (x, y, SLAB + 0.03), black, segments=12, parent=o)
            D.shard_scatter(5, (x - r * 1.6, y - r * 1.6, x + r * 1.6, y + r * 1.6), z=SLAB, size=(0.2, 0.5),
                            seed=i, parent=o)
    return D.done(o)


FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 24, "target_z": 0.0}
