"""Russian Sniper (SN.russia).
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "SVD Dragunov" by neyr (CC-BY-4.0, sketchfab.com/3d-models/svd-dragunov-b18837e316304521a5d2da8d258b6f25).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("russia", "svd", "long")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
