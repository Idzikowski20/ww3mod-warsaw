"""PBOX: pillbox, from "German Bunker" by Tactical_Gamer (CC-BY-4.0, sketchfab.com/3d-models/german-bunker-65a0b82826f440d9aef3181946881c2b).
A cast-concrete fighting bunker with a firing slit in front and two splinter walls flanking the entrance at
the back; the source (2 units wide) is scaled x3 to a real 6 m with walls, 3.2 m tall. Earth is banked
against its flanks, sandbags close the entrance."""

import math
import convert
import _defences as D
from lib import box, mat

SOURCE = "german_bunker.glb"
K = 3.0


def bunker(wreck=False, sink=0.0):
    """The bunker (front +y), standing sink metres into the ground; wreck cracks the roof and blows a corner."""
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    p = D.fit(o, rot=180, k=K, lift=-sink)
    if wreck:  # the roof's front corner breaks off and drops
        parts = convert.split(o, {"chunk": lambda c: c.x > 0.7 and c.y > 0.0 and c.z > 2.0 - sink}, rest="hull")
        chunk = parts.get("chunk")
        if chunk:
            convert.pivot(chunk, (0.7, 0.0, 2.0 - sink))
            convert.parent(chunk, o)
            chunk.rotation_euler = (0.25, 0.35, 0.1)
            chunk.location.z -= 0.35
    return o


def build(wreck=False):
    o = bunker(wreck)
    # Earth banked against the flanks and the back corners.
    for side in (-1, 1):
        D.mound("bank", (2.2, 4.4), 1.5, loc=(side * 2.3, -0.3, 0), top=0.3, parent=o, seed=side + 3)
    D.sandbag_row((-0.9, -1.75, 0), (0.9, -1.75, 0), layers=2, parent=o)  # entrance blast wall
    if wreck:
        D.shard_scatter(9, (-2.8, 1.2, 2.8, 3.4), parent=o)
    return D.done(o)


FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 13, "target_z": 1.0}
