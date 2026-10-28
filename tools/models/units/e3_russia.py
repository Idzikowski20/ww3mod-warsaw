"""Russian Rifleman (E3.russia, veteran E3R1.russia): rifle, launcher on the back.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Ak47" by wburton (CC-BY-4.0, sketchfab.com/3d-models/ak47-831519a097d84e079fd8bc4b15e5b57d).
- "RPG-7" by paolinorenzo (CC-BY-4.0, sketchfab.com/3d-models/rpg-7-6c8683f0dbc04d75b610a2e656e639a8).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("rpg", "launcher"), rot=(90, 25, 0), height=0.22)


def build(wreck=False):
    return inf.soldier("russia", "ak", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
