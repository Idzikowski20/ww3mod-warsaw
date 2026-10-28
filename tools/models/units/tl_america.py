"""US Team leader (TL.america): rifle, radio backpack.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "M4 Carbine" by SINNIK (CC-BY-4.0, sketchfab.com/3d-models/m4-carbine-b516a8416b1044a7839b4a89dc24ca38).
- "Military/Tactical Radio & Backpack" by Neslihan Çakmak (CC-BY-4.0, sketchfab.com/3d-models/militarytactical-radio-backpack-8209d4ac220e4ae09cadd9be49a5119f), voxel-rebuilt.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("radio", "radio"), height=0.2)


def build(wreck=False):
    return inf.soldier("america", "m4", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
