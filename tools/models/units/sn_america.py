"""US Sniper (SN.america).
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "KAC M110" by CloudyRain (CC-BY-4.0, sketchfab.com/3d-models/kac-m110-df9e38fe9c674c30bd212daccd11414a).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("america", "m110", "long")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
