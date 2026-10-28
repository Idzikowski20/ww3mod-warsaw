"""Russian Mortarman (MT.russia): rifle, mortar on the back.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Ak47" by wburton (CC-BY-4.0, sketchfab.com/3d-models/ak47-831519a097d84e079fd8bc4b15e5b57d).
- "Mortar - M224" by jcherry3d (CC-BY-4.0, sketchfab.com/3d-models/mortar-m224-c86a73e40d994431bcdb57dc741cf8be), voxel-rebuilt.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("mortar", "mortar"), rot=(0, 10, 0), height=0.12)


def build(wreck=False):
    return inf.soldier("russia", "ak", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
