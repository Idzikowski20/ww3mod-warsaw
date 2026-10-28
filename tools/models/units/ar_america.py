"""US Machine gunner (AR.america).
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "M249 DIY builds (2)" by Nortenko Dmytro (CC-BY-4.0, sketchfab.com/3d-models/m249-diy-builds-2-c489c3bf18ee487186469cca48b56c82), voxel-rebuilt.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("america", "m249", "long")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
