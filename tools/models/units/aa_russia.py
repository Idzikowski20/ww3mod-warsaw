"""Russian Anti-air (AA.russia): Stinger.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "FIM-92 Stinger" by Mortavex (CC-BY-4.0, sketchfab.com/3d-models/fim-92-stinger-d9de43d3b00a4381b991c35369b5e183; file fim-92_stinger_v2.glb).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("russia", "stinger", "launcher")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
