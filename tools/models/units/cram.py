"""CRAM: the land-based Phalanx (C-RAM, Centurion), from "C-RAM" by grandsnail7000 (CC-BY-4.0,
sketchfab.com/3d-models/c-ram-484eaa8b14cd452cb7eb9aaf600619b9). The source is real size (4.9 m tall, base
2.6 m wide), its gun along +Y. The mount above the training ring (radome, yoke, M61 gun) is the turret,
cut by height; it stands on a cast concrete pad, as the C-RAM sites on FOBs do."""

import convert
import _defences as D
from lib import box, mat

SOURCE = "c-ram.glb"
RING_Z = -1.08   # source height of the training ring's top (the turntable disc is -1.31..-1.03)
PAD = 0.25
GUN_PIVOT = (0.0, 0.3, 0.08)  # source: the gun's elevation trunnion inside the yoke


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.decimate(o, 11000)
    # Haze grey all over (the source is near black), radome off-white, the gun and its feed dark.
    D.paint(o, {"Material.003": (0.7, 0.71, 0.7), "Material.001": (0.12, 0.12, 0.12),
                "Material.002": (0.08, 0.08, 0.08), "CW-Silver-matte": (0.3, 0.31, 0.32),
                "Material.010": (0.05, 0.06, 0.1)}, default=(0.43, 0.45, 0.46))
    p = D.fit(o, rot=0, k=1.0, centre=(0, -0.43, 0), lift=PAD)  # the cabinet's centre
    ring = p(0, 0, RING_Z)
    parts = convert.split(o, {
        "barrel": lambda c: abs(p.src(c).x) < 0.12 and p.src(c).y > 0.55 and -0.02 < p.src(c).z < 0.2,
        "turret": lambda c: c.z > ring[2],
    }, rest="hull")
    hull, turret, barrel = parts["hull"], parts["turret"], parts["barrel"]
    convert.pivot(turret, ring)
    convert.pivot(barrel, p(*GUN_PIVOT))
    convert.parent(barrel, turret)
    convert.parent(turret, hull)

    D.pad("pad", (3.9, 3.9), height=PAD, parent=hull)  # 7.8 m at Scale 2: one cell
    return D.done(hull)


WRECK = False  # no CRAM husk
FINISH = {"flat": False, "keep": ("hull", "turret", "barrel")}
PREVIEW = {"distance": 12, "target_z": 2.0}
