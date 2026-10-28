"""HSAM: camouflaged S-300 site - a 5P85SE launcher (MAZ-543M) dug in, from "USSR "S-300" SAM 5P85SE (War
Thunder AF!)" by KojfDiscord (CC-BY-4.0, sketchfab.com/3d-models/ussr-s-300-sam-5p85se-war-thunder-af-da04a49123d143adbc1d39ac6ba6e33f).
Scaled to the real 13 m. The truck lies along x (2 x 1 cells), cab east, sunk a metre into a revetment: an
earth berm round it, sandbags on the crest, camouflage netting on poles over the cab and chassis, the four
launch tubes erect through a gap at the rear. The tubes stand vertical, so they need no turret node."""

import math
import convert
import _defences as D
from lib import box, mat
from mathutils import Matrix

SOURCE = "ussr_s-300_sam_5p85se_war_thunder_af.glb"
K = 13.0 / 13.94
SINK = 0.9


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.decimate(o, 8500)
    convert.raw_colours(o)
    p = D.fit(o, rot=90, k=K, lift=-SINK)
    parts = convert.split(o, {"tubes": lambda c: p.src(c).y > 5.1 and p.src(c).z > 1.0}, rest="hull")
    hull = parts["hull"]
    tubes = parts.get("tubes")
    if tubes:
        convert.pivot(tubes, p(0, 5.9, 0.6))
        convert.parent(tubes, hull)

    # Revetment: earth berm round the truck, open behind the tubes for the crew; sandbags on the crest.
    D.berm("berm", (7.6, 3.6), (6.9, 2.5), 1.35, parent=hull)
    D.sandbag_row((-6.6, 2.6, 1.15), (5.8, 2.6, 1.15), layers=1, parent=hull)  # one side only: 15k budget
    # Netting over the cab and the chassis (not over the erect tubes at the rear).
    net = D.camo_net("net", (9.5, 6.4), (1.4, 0, 0), height=3.9, droop=2.6, parent=hull, res=12,
                     holes=0.15 if wreck else 0.0)

    if wreck:
        if tubes:
            tubes.rotation_euler = (0.25, -0.5, 0.1)
        net.location.z -= 0.8
    return D.done(hull)


FINISH = {"flat": False, "keep": ("hull",)}
PREVIEW = {"distance": 27, "target_z": 1.5}
