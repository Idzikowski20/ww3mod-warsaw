"""Russian Technician (TECN.russia): no long weapon, tool bag.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.in_hand(fig, inf.tool_bag())


def build(wreck=False):
    return inf.soldier("russia", None, kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
