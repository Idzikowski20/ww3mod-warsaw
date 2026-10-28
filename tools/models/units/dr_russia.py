"""Russian Drone operator (DR.russia): controller in hand, rifle slung.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Ak47" by wburton (CC-BY-4.0, sketchfab.com/3d-models/ak47-831519a097d84e079fd8bc4b15e5b57d).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.weapon("ak", name="slung")[0], rot=(90, 40, 0), height=0.15)


def build(wreck=False):
    return inf.soldier("russia", "tablet", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
