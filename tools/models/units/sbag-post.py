"""SBAG post: a squat stack of sandbags (two layers of the pile from "Military/Urban Prop Set" by Neslihan
Cakmak, CC-BY-4.0, sketchfab.com/3d-models/militaryurban-prop-set-fc57f8223fbc4ec8a10e74cd43e735f1, cut down
to 1.4 m square) at the origin, 1.1 m high, a marker stake in it. Segments run along +y."""

import _defences as D
from lib import box, cyl, mat


def build(wreck=False):
    o = D.prop("sandbag", (0, 0, 0), rot=90, scale=(0.66, 1.0, 1.0))
    o.name = "hull"
    D.prop("sandbag", (0, 0, 0.5), rot=0, scale=(0.62, 1.0, 1.0), parent=o)
    cyl("stake", 0.04, 1.6, (0.35, -0.35, 0.8), mat("wood", D.WOOD), segments=5, parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 7, "target_z": 0.5}
