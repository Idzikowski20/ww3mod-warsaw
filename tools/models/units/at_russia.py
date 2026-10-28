"""Russian Anti-tank (AT.russia): Javelin.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "FGM-148 Javelin" by STALKER (CC-BY-4.0, sketchfab.com/3d-models/fgm-148-javelin-d8fe79b60b2d42308e11fbd22f4dec4f).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("russia", "javelin", "launcher")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
