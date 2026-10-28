"""Russian Machine gunner (AR.russia).
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "PKM Machine Gun" by Li Zheng (CC-BY-4.0, sketchfab.com/3d-models/pkm-machine-gun-79bc67a78b434e65950f0257fe5f09a5).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("russia", "pkm", "long")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
