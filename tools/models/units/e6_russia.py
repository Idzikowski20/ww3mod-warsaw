"""Russian Combat engineer (E6.russia): MP5, shovel on the back.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Mp5" by Long Nguyễn (CC-BY-4.0, sketchfab.com/3d-models/mp5-fa9b8914fda34acb9a54fa64e99d5608).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.shovel(), rot=(90, -30, 0), height=0.15)


def build(wreck=False):
    return inf.soldier("russia", "mp5", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
