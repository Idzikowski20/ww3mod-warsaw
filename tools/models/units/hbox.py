"""HBOX: camouflaged pillbox - the PBOX bunker ("German Bunker" by Tactical_Gamer, CC-BY-4.0,
sketchfab.com/3d-models/german-bunker-65a0b82826f440d9aef3181946881c2b) sunk 1.9 m into the ground so only
its roof and firing slit show, sandbags round the edge, under a low camouflage net."""

import _defences as D
from pbox import bunker

SINK = 1.9


def build(wreck=False):
    o = bunker(wreck, sink=SINK)
    D.berm("spoil", (3.6, 3.3), (2.9, 2.5), 0.55, parent=o, segments=20)
    # Sandbags on the spoil round the flanks and either side of the firing slit (not in front of it).
    for a, b in (((-2.9, 2.4, 0.3), (-1.4, 2.4, 0.3)), ((1.4, 2.4, 0.3), (2.9, 2.4, 0.3)),
                 ((-3.0, -2.2, 0.3), (-3.0, 2.0, 0.3)), ((3.0, -2.2, 0.3), (3.0, 2.0, 0.3))):
        D.sandbag_row(a, b, layers=1, parent=o, seed=int(a[0] * 10))
    # The net covers the roof and back, its front edge just over the slit.
    D.camo_net("net", (7.4, 4.8), (0, -0.9, 0), height=1.6, droop=1.4, parent=o, res=16, poles=False,
               holes=0.2 if wreck else 0.0)
    if wreck:
        D.shard_scatter(7, (-2.6, 1.8, 2.6, 3.4), parent=o)
    return D.done(o)


FINISH = {"flat": False, "keep": ("hull",), "texture_size": 512}
PREVIEW = {"distance": 13, "target_z": 0.5}
