"""US Technician (TECN.america): no long weapon, tool bag.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.in_hand(fig, inf.tool_bag())


def build(wreck=False):
    return inf.soldier("america", None, kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
