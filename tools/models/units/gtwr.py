"""GTWR: guard tower, from "Watch tower" by _SeF_ (CC-BY-4.0, sketchfab.com/3d-models/watch-tower-042f327a0f4c4fc9bf458903666bb257).
The source is in centimetres: a 12.6 m steel lattice tower on four concrete footings, 5.2 m square, three
flights of stairs, a timber observation deck with railings, a searchlight and a camouflage-net
awning."""

import convert
import _defences as D
from lib import box

SOURCE = "watch_tower.glb"


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    D.fit(o, rot=0, k=0.01)
    return D.done(o)


WRECK = False  # no GTWR husk
FINISH = {"flat": False, "keep": ("hull",), "texture_size": 1024}
PREVIEW = {"distance": 26, "target_z": 6.0}
