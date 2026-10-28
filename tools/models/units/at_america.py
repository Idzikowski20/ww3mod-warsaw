"""US Anti-tank (AT.america): Javelin.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "FGM-148 Javelin" by STALKER (CC-BY-4.0, sketchfab.com/3d-models/fgm-148-javelin-d8fe79b60b2d42308e11fbd22f4dec4f).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("america", "javelin", "launcher")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
