"""LOGISTICSCENTER: forward logistics / service depot, hand-built with props from "Military/Urban Prop Set"
by Neslihan Çakmak (CC-BY-4.0, sketchfab.com/3d-models/militaryurban-prop-set-fc57f8223fbc4ec8a10e74cd43e735f1):
sandbags, concrete jersey barriers, tyres. On a concrete hardstand 10.7 m square (2 x 2 cells at Scale 1.5):
the service bay (the south-west dock cell, where vehicles park to be repaired and rearmed) under a gantry
crane with a chain hoist; an arched fabric maintenance shelter; two 20 ft containers (stores and the
workshop); a fuel bladder behind a sandbag wall; ammunition pallets, tyres, barriers and barriers."""

import _defences as D
from lib import box, cyl, mat

H = 5.33  # half the site, model metres


def build(wreck=False):
    steel = mat("steel", D.STEEL)
    yellow = mat("hazard", D.YELLOW)
    black = mat("black", D.BLACK)
    hull = D.root(D.pad("hull", (2 * H, 2 * H), height=0.2))
    D.bay_lines("bay", (4.6, 4.6), (-2.65, -2.65, 0.2), parent=hull)

    # Gantry crane over the service bay: two A-frame legs, a beam, the hoist and its hook.
    gx, gy = -2.65, -2.65
    for dx in (-2.4, 2.4):
        for dy in (-0.9, 0.9):
            box("gantry_leg", (0.18, 0.18, 4.6), (gx + dx, gy + dy * 0.55, 2.5), yellow, parent=hull,
                rot=(dy * 9, 0, 0))
        box("gantry_foot", (0.4, 2.2, 0.2), (gx + dx, gy, 0.3), steel, parent=hull)
    beam = box("gantry_beam", (5.2, 0.3, 0.35), (gx, gy, 4.85), yellow, parent=hull)
    if wreck:
        beam.rotation_euler = (0, 0.5, 0.1)
        beam.location.z -= 1.6
    box("hoist", (0.5, 0.45, 0.45), (gx + 0.6, gy, 4.45), black, parent=hull)
    cyl("chain", 0.03, 2.2, (gx + 0.6, gy, 3.1), steel, segments=4, parent=hull)
    box("hook", (0.15, 0.08, 0.3), (gx + 0.6, gy, 1.9), black, parent=hull)
    box("engine_pack", (1.4, 1.0, 0.9), (gx - 1.1, gy + 1.5, 0.65), mat("olive", D.OLIVE), parent=hull, bevel=0.04)

    # Maintenance shelter over the north-east quarter, open toward the yard.
    sh = D.shelter("shelter", (4.8, 5.6), (2.6, 2.4, 0.2), rot=180, parent=hull)
    if wreck:
        sh.scale = (1.0, 1.0, 0.55)
        sh.rotation_euler = (0.08, -0.1, 3.14)

    # Two containers stacked along the north-west edge (stores on the workshop).
    D.container("container", (-2.6, 3.9, 0.2), rot=0, parent=hull)
    D.container("container2", (-2.2, 3.9, 2.79), rot=0, colour=(0.36, 0.33, 0.24), parent=hull)

    # Fuel point: bladder behind sandbags in the south-east corner; ammunition pallets; tyres; barriers.
    D.bladder("bladder", (3.2, 2.0), (2.7, -3.4, 0.2), parent=hull)
    D.sandbag_row((0.7, -5.0, 0.2), (5.0, -5.0, 0.2), layers=1, parent=hull)
    D.sandbag_row((5.0, -4.8, 0.2), (5.0, -1.6, 0.2), layers=1, parent=hull, seed=2)
    for i, (x, y) in enumerate(((0.9, -1.0), (2.2, -1.1))):
        D.crates("ammo", (x, y, 0.2), n=8 if i else 6, rot=8 * i, parent=hull, seed=i)
    for i in range(4):
        D.prop("tyre_flat", (4.5, -0.7, 0.2 + i * 0.24), rot=i * 40, parent=hull)
    D.prop("tyre", (4.6, 0.5, 0.2), rot=80, tilt=(0, 12), parent=hull)
    for x in (-4.6, -1.4):
        D.jersey((x, -5.0, 0.2), rot=0, parent=hull)
    if wreck:
        D.shard_scatter(10, (-H, -H, H, H), z=0.2, parent=hull)
    return D.done(hull)


WRECK = False  # no LOGISTICSCENTER husk
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 22, "target_z": 1.0}
