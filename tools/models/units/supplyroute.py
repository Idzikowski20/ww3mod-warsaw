"""SUPPLYROUTE: the supply route's entry checkpoint, hand-built with props from "Military/Urban Prop Set" by
Neslihan Çakmak (CC-BY-4.0, sketchfab.com/3d-models/militaryurban-prop-set-fc57f8223fbc4ec8a10e74cd43e735f1):
sandbags, concrete jersey barriers, tyres. A crossroads of two 5.3 m roads over the 3 x 3 cell site (16 m
square model at Scale 1.5), the arms through the middle cells that reinforcements drive along, the corners
fortified: a guard booth with a boom barrier, a HESCO-walled sandbag position, a container store with tyres,
and a sign post with the route arrows."""

import math
import _defences as D
from lib import box, cyl, mat

H = 8.0       # half the site
R = 2.65      # half a road


def build(wreck=False):
    asphalt = mat("asphalt", (0.2, 0.2, 0.2))
    gravel = mat("gravel", (0.4, 0.37, 0.31))
    white = mat("white", (0.8, 0.8, 0.78))
    red = mat("marker_red", (0.7, 0.12, 0.08))
    steel = mat("steel", D.STEEL)
    wood = mat("wood", D.WOOD)
    glass = mat("glass", (0.18, 0.28, 0.32))
    hull = D.root(box("hull", (2 * H, 2 * R, 0.1), (0, 0, 0.05), asphalt))
    box("road_ns", (2 * R, 2 * H, 0.1), (0, 0, 0.05), asphalt, parent=hull)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("corner", (H - R - 0.1, H - R - 0.1, 0.06), (sx * (H + R) / 2, sy * (H + R) / 2, 0.03), gravel, parent=hull)
    for i in range(5):  # dashed centre lines on all four arms
        t = R + 0.6 + i * 1.05
        for a in (0, 90, 180, 270):
            x, y = math.cos(math.radians(a)) * t, math.sin(math.radians(a)) * t
            box("dash", (0.6, 0.12, 0.02) if a in (0, 180) else (0.12, 0.6, 0.02), (x, y, 0.11), white, parent=hull)

    # North-east: guard booth, its boom barrier across the north arm (raised).
    bx, by = R + 1.6, R + 1.7
    box("booth", (2.0, 2.0, 2.4), (bx, by, 1.2), mat("booth", (0.42, 0.42, 0.36)), parent=hull, bevel=0.03)
    box("booth_roof", (2.4, 2.4, 0.15), (bx, by, 2.47), mat("olive", D.OLIVE), parent=hull)
    for side in (-1, 1):
        box("booth_window", (0.04, 1.4, 0.6), (bx + side * 1.01, by, 1.6), glass, parent=hull)
    box("booth_window", (1.4, 0.04, 0.6), (bx, by - 1.01, 1.6), glass, parent=hull)
    box("boom_post", (0.3, 0.3, 1.0), (R + 0.3, R + 3.6, 0.5), steel, parent=hull)
    for k in range(6):  # red and white boom, raised at 75 degrees
        a = math.radians(75)
        d = 0.35 + k * 0.85
        box("boom", (0.85, 0.1, 0.1), (R + 0.3 - math.cos(a) * d, R + 3.6, 1.0 + math.sin(a) * d),
            red if k % 2 == 0 else white, parent=hull, rot=(0, 75, 0))

    # North-west: HESCO walls on the outer edges round a sandbagged fighting position.
    D.hesco((-H + 0.6, H - 0.6, 0.06), (-R - 0.8, H - 0.6, 0.06), parent=hull)
    D.hesco((-H + 0.6, H - 1.7, 0.06), (-H + 0.6, R + 0.8, 0.06), parent=hull)
    D.sandbag_row((-R - 1.2, R + 1.0, 0.06), (-R - 1.2, R + 3.4, 0.06), layers=2, parent=hull)

    # South-west: container store and tyres.
    D.container("store", (-(H + R) / 2, -(H + R) / 2 - 0.3, 0.06), rot=0, parent=hull)
    for i in range(5):
        D.prop("tyre_flat", (-R - 1.0, -R - 0.8, 0.06 + i * 0.24), rot=i * 33, parent=hull)
    D.prop("tyre", (-H + 0.8, -R - 0.8, 0.06), rot=10, tilt=(0, 15), parent=hull)

    # South-east: the route sign, barriers and pallets.
    sx, sy = R + 2.2, -R - 2.2
    cyl("sign_post", 0.08, 3.0, (sx, sy, 1.5), wood, segments=6, parent=hull)
    for k, (z, a) in enumerate(((2.6, 0), (2.2, 90), (1.8, 200))):
        b = box("sign_board", (1.4, 0.05, 0.3), (0, 0, 0), white, parent=hull, rot=(0, 0, a))
        b.location = (sx + math.cos(math.radians(a)) * 0.65, sy + math.sin(math.radians(a)) * 0.65, z)
    for x in (R + 1.8, R + 4.9):
        D.jersey((x, -R - 0.5, 0.06), rot=0, parent=hull)
    D.crates("ammo", (H - 1.4, -H + 1.3, 0.06), n=8, parent=hull)
    D.sandbag_row((H - 0.5, -H + 0.6, 0.06), (H - 0.5, -R - 1.4, 0.06), layers=1, parent=hull)
    return D.done(hull)


WRECK = False  # no SUPPLYROUTE husk
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 30, "target_z": 0.0}
