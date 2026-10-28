"""SBAG segment: a sandbag wall 1.1 m high and 1.3 m thick from y = 0 to 4 (one cell at Scale 2), two
layers of the pile from "Military/Urban Prop Set" by Neslihan Cakmak (CC-BY-4.0,
sketchfab.com/3d-models/militaryurban-prop-set-fc57f8223fbc4ec8a10e74cd43e735f1), the top layer offset half
a pile like laid bags."""

import _defences as D


def build(wreck=False):
    o = D.prop("sandbag", (0, 1.0, 0), rot=90, scale=(0.98, 1.0, 1.0))
    o.name = "hull"
    D.prop("sandbag", (0, 3.0, 0), rot=90, scale=(0.98, 1.0, 1.0), parent=o)
    D.prop("sandbag", (0, 2.0, 0.5), rot=90, scale=(0.98, 0.92, 1.0), parent=o)
    D.prop("sandbag", (0, 0.45, 0.5), rot=90, scale=(0.45, 0.92, 1.0), parent=o)
    D.prop("sandbag", (0, 3.55, 0.5), rot=90, scale=(0.45, 0.92, 1.0), parent=o)
    return D.done(o)


WRECK = False
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 9, "target_z": 0.5}
