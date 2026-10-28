"""Russian Grenadier (E2.russia, veteran E2R1.russia).
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Ak47" by wburton (CC-BY-4.0, sketchfab.com/3d-models/ak47-831519a097d84e079fd8bc4b15e5b57d).
- "low-poly GP-25" by D.U. (CC-BY-4.0, sketchfab.com/3d-models/low-poly-gp-25-8dbdec74bad944a9b7eca73b2a6269fa).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def build(wreck=False):
    return inf.soldier("russia", "ak_gp25")


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
