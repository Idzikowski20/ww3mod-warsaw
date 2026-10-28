"""US vehicle crew (crew.driver/gunner/commander.america): MP5.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "Mp5" by Long Nguyễn (CC-BY-4.0, sketchfab.com/3d-models/mp5-fa9b8914fda34acb9a54fa64e99d5608).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("america", "mp5")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
