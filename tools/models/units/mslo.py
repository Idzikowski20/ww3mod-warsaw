"""MSLO: nuclear missile silo, hand-built (no CC source). The headworks of a silo launcher as seen above
ground: a concrete apron, the raised collar over the shaft closed by a sliding blast door (a 4 m square
steel-and-concrete slab) that runs off on two rails, the crew access hatch, ventilation stacks and an HF whip
antenna. Real size 10.4 x 5.2 m apron; the door slides along x (the site is 2 x 1 cells)."""

import math
import _defences as D
from lib import box, cyl, extrude, mat

DOOR_X = -2.2   # shaft centre


def build(wreck=False):
    concrete = mat("concrete", D.CONCRETE)
    dark = mat("concrete_dark", D.CONCRETE_DARK)
    steel = mat("steel", D.STEEL)
    black = mat("black", D.BLACK)
    yellow = mat("hazard", D.YELLOW)
    olive = mat("olive", D.OLIVE)

    hull = D.root(D.pad("hull", (10.4, 5.2), height=0.3))
    D.pad("apron_edge", (10.8, 5.6), height=0.12, material=dark, parent=hull)
    # Collar over the shaft, with its own chamfered lip.
    sq = [(-2.2, -2.2), (2.2, -2.2), (2.2, 2.2), (-2.2, 2.2)]
    extrude("collar", sq, 0.7, (DOOR_X, 0, 0.3), concrete, top_scale=0.94, parent=hull, bevel=0.04)
    # Rails: from under the door to where it rolls when open, on a sleeper strip.
    for y in (-1.6, 1.6):
        box("rail_bed", (9.6, 0.6, 0.18), (0.4, y, 0.39), dark, parent=hull)
        box("rail", (9.6, 0.14, 0.16), (0.4, y, 0.56), steel, parent=hull)
        box("rail_stop", (0.3, 0.5, 0.45), (5.05, y, 0.55), yellow, parent=hull)
    # Crew access hatch with a hand rail, vents, antenna, a cable trench cover.
    box("hatch_curb", (1.2, 1.2, 0.35), (3.6, -2.05, 0.45), concrete, parent=hull, bevel=0.03)
    box("hatch", (0.9, 0.9, 0.08), (3.6, -2.05, 0.66), steel, parent=hull)
    box("hatch_wheel", (0.4, 0.06, 0.06), (3.6, -2.05, 0.73), black, parent=hull)
    for i, x in enumerate((2.6, 3.6)):
        cyl("vent", 0.22, 1.2, (x, 2.1, 0.9), steel, segments=10, parent=hull)
        cyl("vent_cap", 0.34, 0.12, (x, 2.1, 1.58), steel, segments=10, parent=hull, radius2=0.12)
    cyl("antenna", 0.04, 6.5, (4.8, 2.25, 3.55), steel, segments=6, parent=hull)
    box("antenna_box", (0.5, 0.4, 0.6), (4.8, 1.85, 0.6), olive, parent=hull, bevel=0.02)
    box("cable_cover", (3.0, 0.5, 0.06), (2.5, -0.0, 0.33), dark, parent=hull)
    for k in range(5):  # hazard chevrons painted at the door's run-off end
        box("chevron", (0.25, 3.0, 0.02), (4.0 + k * 0.0, 0, 0.31), yellow if k % 2 == 0 else black, parent=hull,
            rot=(0, 0, 0)).location.x = 3.4 + k * 0.3 - 0.0

    if wreck:
        # Door blown off its rails and thrown askew; the shaft open and black; rubble.
        cyl("shaft", 1.7, 0.1, (DOOR_X, 0, 0.98), black, segments=20, parent=hull)
        door = box("door", (4.0, 4.0, 0.9), (DOOR_X + 3.2, 0.9, 1.4), dark, parent=hull, bevel=0.05,
                   rot=(18, -32, 14))
        D.shard_scatter(14, (-5.2, -2.8, 2.0, 2.8), z=0.3, parent=hull)
    else:
        door = box("door", (4.0, 4.0, 0.9), (DOOR_X, 0, 1.45), dark, parent=hull, bevel=0.05)
        box("door_skin", (3.8, 3.8, 0.05), (DOOR_X, 0, 1.92), steel, parent=hull)
        for y in (-1.6, 1.6):  # the door's bogies on the rails
            for x in (-1.5, 1.5):
                box("bogie", (0.7, 0.3, 0.4), (DOOR_X + x, y, 0.84), steel, parent=hull)
        for x in (-1.95, 1.95):  # hazard stripes on its leading edges
            box("door_hazard", (0.08, 3.9, 0.2), (DOOR_X + x, 0, 1.75), yellow, parent=hull)
        for dx in (-1.4, 1.4):  # lifting lugs and the seam of the door's two cast halves
            for dy in (-1.4, 1.4):
                box("lug", (0.25, 0.12, 0.2), (DOOR_X + dx, dy, 2.02), steel, parent=hull)
        box("seam", (0.06, 3.8, 0.02), (DOOR_X - 0.9, 0, 1.95), black, parent=hull)
        box("seam", (0.06, 3.8, 0.02), (DOOR_X + 0.9, 0, 1.95), black, parent=hull)
    return D.done(hull)


FINISH = {"flat": True, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 21, "target_z": 0.8}
