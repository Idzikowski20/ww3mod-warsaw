"""Russian Team leader (TL.russia): rifle, radio backpack.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- "Ak47" by wburton (CC-BY-4.0, sketchfab.com/3d-models/ak47-831519a097d84e079fd8bc4b15e5b57d).
- "Military/Tactical Radio & Backpack" by Neslihan Çakmak (CC-BY-4.0, sketchfab.com/3d-models/militarytactical-radio-backpack-8209d4ac220e4ae09cadd9be49a5119f), voxel-rebuilt.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("radio", "radio"), height=0.2)


def build(wreck=False):
    return inf.soldier("russia", "ak", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
