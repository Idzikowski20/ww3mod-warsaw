"""FTUR: flame turret, hand-built (no CC source exists). After the cameo: a cast concrete base with a steel
pedestal, on it an armoured turret with a heavy flame projector in a shrouded mount (the ranged turret), its
pressurised fuel and propellant bottles armoured at the rear; round the pedestal a low traversing collar with
two short spray nozzles for close defence (the melee turret). Fuel comes from a buried tank beside the base.
Real size: base 4.6 m across, 3.3 m to the turret roof."""

import math
import _defences as D
from lib import box, cyl, extrude, prism, mat

BASE = 1.1      # concrete base height
PED = 0.75      # pedestal height above it


def build(wreck=False):
    concrete = mat("concrete", D.CONCRETE)
    dark = mat("concrete_dark", D.CONCRETE_DARK)
    olive = mat("olive", D.OLIVE)
    olive_dark = mat("olive_dark", (0.2, 0.21, 0.13))
    steel = mat("steel", D.STEEL)
    black = mat("black", D.BLACK)
    yellow = mat("hazard", D.YELLOW)
    glass = mat("glass", (0.18, 0.28, 0.32))

    octagon = [(2.3 * math.cos(math.radians(22.5 + 45 * i)), 2.3 * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    hull = extrude("hull", octagon, BASE, material=concrete, top_scale=0.9, bevel=0.04)
    extrude("footing", [(x * 1.07, y * 1.07) for x, y in octagon], 0.15, material=dark, top_scale=0.97, parent=hull)
    # Hazard band round the base's crown and an access hatch, the buried fuel tank's fill point and pipe.
    for i in range(8):
        a = math.radians(45 * i)
        b = box("hazard", (1.45, 0.04, 0.14), (0, 0, 0), yellow, parent=hull, rot=(0, 0, math.degrees(a) + 90))
        b.location = (2.03 * math.cos(a), 2.03 * math.sin(a), BASE - 0.12)
    box("hatch", (0.9, 0.06, 0.8), (0, -2.14, 0.55), steel, parent=hull, rot=(-6, 0, 0))
    cyl("fill_point", 0.32, 0.35, (-2.6, -1.6, 0.17), steel, segments=10, parent=hull)
    cyl("fill_cap", 0.36, 0.08, (-2.6, -1.6, 0.38), black, segments=10, parent=hull)
    box("fuel_pipe", (1.2, 0.14, 0.14), (-1.95, -1.35, 0.12), steel, parent=hull, rot=(0, 0, 24))
    cyl("pedestal", 0.72, PED, (0, 0, BASE + PED / 2), olive_dark, segments=16, parent=hull)
    cyl("pedestal_flange", 0.95, 0.1, (0, 0, BASE + 0.05), steel, segments=16, parent=hull)

    # Melee turret: a traversing collar round the pedestal with two short spray nozzles.
    turret2 = cyl("turret2", 0.98, 0.32, (0, 0, BASE + 0.32), olive, segments=16, bevel=0.03)
    turret2.parent = hull
    for x in (-0.38, 0.38):
        box("spray_mount", (0.28, 0.4, 0.26), (x, 0.95, 0.0), olive_dark, parent=turret2, bevel=0.02)
        cyl("spray", 0.07, 0.55, (x, 1.35, 0.03), steel, axis="Y", segments=8, parent=turret2)
        cyl("spray_tip", 0.1, 0.08, (x, 1.64, 0.03), black, axis="Y", segments=8, parent=turret2)

    # Ranged turret: armoured housing, sloped glacis and cheeks.
    turret = prism("turret", [(-1.25, 0.0), (1.05, 0.0), (1.45, 0.5), (0.95, 1.15), (-1.15, 1.15), (-1.35, 0.6)],
                   2.1, material=olive, bevel=0.03)
    turret.location = (0, 0, BASE + PED)
    turret.parent = hull
    box("roof_plate", (1.8, 1.6, 0.06), (0, -0.15, 1.18), olive_dark, parent=turret, bevel=0.02)
    box("cupola", (0.6, 0.6, 0.25), (-0.45, -0.35, 1.3), olive_dark, parent=turret, bevel=0.03)
    box("vision", (0.4, 0.06, 0.1), (-0.45, -0.04, 1.33), glass, parent=turret)
    box("sight", (0.25, 0.3, 0.3), (0.55, 0.65, 1.3), olive_dark, parent=turret, bevel=0.02)
    box("sight_glass", (0.18, 0.02, 0.14), (0.55, 0.81, 1.32), glass, parent=turret)
    # Armoured bottles at the rear: fuel (thick) and nitrogen propellant (thin), strapped in a cage.
    for x in (-0.55, 0.55):
        cyl("fuel_bottle", 0.36, 1.1, (x, -1.55, 0.62), olive_dark, segments=14, parent=turret, bevel=0.06)
        cyl("bottle_cap", 0.16, 0.12, (x, -1.55, 1.22), steel, segments=8, parent=turret)
        for z in (0.25, 0.95):
            cyl("bottle_strap", 0.37, 0.05, (x, -1.55, z), black, segments=14, parent=turret)
    cyl("n2_bottle", 0.17, 1.0, (0, -1.62, 0.55), steel, segments=10, parent=turret)
    box("bottle_guard", (2.0, 0.06, 0.9), (0, -1.97, 0.55), olive, parent=turret)

    # The flame projector (barrel): shrouded tube, igniter housing, flash guard, fuel hose.
    barrel = box("barrel", (0.5, 0.5, 0.5), (0, 1.25, 0.62), olive_dark, bevel=0.04)  # mantlet
    barrel.parent = turret
    cyl("projector_shroud", 0.16, 1.5, (0, 0.95, 0.0), olive, axis="Y", segments=12, parent=barrel)
    cyl("projector_tube", 0.09, 0.4, (0, 1.85, 0.0), steel, axis="Y", segments=10, parent=barrel)
    cyl("nozzle", 0.13, 0.12, (0, 2.08, 0.0), black, axis="Y", segments=10, parent=barrel)
    box("igniter", (0.16, 0.5, 0.16), (0, 1.4, -0.22), steel, parent=barrel)
    box("pilot_light", (0.06, 0.08, 0.06), (0, 1.66, -0.22), mat("ember", (0.9, 0.45, 0.1)), parent=barrel)
    cyl("hose", 0.06, 1.6, (0.32, -0.6, -0.15), black, axis="Y", segments=6, parent=barrel)

    if wreck:
        turret.location = (0.5, -0.3, BASE + PED + 0.1)
        turret.rotation_euler = (0.18, 0.32, 0.7)
        barrel.rotation_euler = (-0.3, 0.1, 0)
        turret2.rotation_euler = (0.04, -0.06, 0.9)
        D.shard_scatter(8, (-3.0, -3.0, 3.0, 3.0), parent=hull)
        for i in range(5):  # scattered bottles and plates
            box("debris_plate", (0.6, 0.4, 0.05), (-2.6 + i * 1.2, 2.4 - (i % 2) * 4.6, 0.1), olive_dark,
                rot=(10 * i, 20, 37 * i), parent=hull)
    return D.done(hull)


FINISH = {"flat": True, "keep": ("hull", "turret", "turret2", "barrel"), "texture_size": 512}
PREVIEW = {"distance": 12, "target_z": 1.6}
