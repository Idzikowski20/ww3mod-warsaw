"""T-90 main battle tank. Source: the t90icon cameo (a T-90A, Russian green, Shtora dazzlers),
real dimensions: hull 6.86 x 3.78 m with skirts, 2.23 m tall, 6 road wheels a side, 125 mm 2A46."""

from lib import box, cyl, extrude, prism, mat, sphere

GREEN = (0.23, 0.27, 0.15)
DARK_GREEN = (0.17, 0.2, 0.11)
TRACK = (0.11, 0.1, 0.09)
RUBBER = (0.06, 0.06, 0.06)
STEEL = (0.32, 0.32, 0.3)
LENS = (0.75, 0.08, 0.05)
GLASS = (0.18, 0.28, 0.32)


def build(wreck=False):
    k = 0.35 if wreck else 1.0  # wrecks are burnt dark
    g = mat("green", tuple(c * k for c in GREEN))
    dg = mat("green_dark", tuple(c * k for c in DARK_GREEN))
    tr = mat("track", TRACK)
    rb = mat("rubber", RUBBER)
    st = mat("steel", tuple(c * k for c in STEEL))
    team = mat("team", (0.9, 0.9, 0.9))
    lens = mat("lens", LENS if not wreck else (0.1, 0.05, 0.05))
    glass = mat("glass", GLASS)

    # Hull: sloped glacis at the front, short rear slope; sits on the suspension.
    hull = prism("hull", [(-3.35, 0.45), (3.0, 0.45), (3.45, 0.95), (2.15, 1.55), (-3.25, 1.55), (-3.43, 1.15)],
                 3.4, material=g)

    # Engine deck grilles and hatches.
    for y in (-2.1, -2.75):
        box("grille", (2.4, 0.5, 0.06), (0, y, 1.57), dg)
    for x in (-0.9, 0.9):
        box("deck_plate", (0.9, 1.0, 0.05), (x, -1.15, 1.57), dg, bevel=0.02)

    # Driver's hatch and periscopes on the glacis top.
    cyl("driver_hatch", 0.32, 0.08, (0, 2.0, 1.58), dg, segments=12)
    box("periscope", (0.25, 0.08, 0.1), (0, 2.38, 1.6), glass)

    # Glacis ERA (Kontakt-5 plates) and the dozer blade under it.
    for i in range(6):
        x = -1.25 + i * 0.5
        box("glacis_era", (0.46, 0.75, 0.12), (x, 2.82, 1.22), g, bevel=0.02, rot=(-55, 0, 0))
    box("dozer", (3.0, 0.15, 0.35), (0, 3.42, 0.62), dg, rot=(-20, 0, 0))

    # Suspension: road wheels, drive sprocket at the rear, idler at the front, return rollers.
    for side in (-1, 1):
        x = side * 1.45
        for i in range(6):
            y = -2.45 + i * 0.93
            cyl("wheel", 0.38, 0.26, (x, y, 0.42), st, axis="X", segments=14, bevel=0.03)
            cyl("hub", 0.13, 0.3, (x, y, 0.42), dg, axis="X", segments=8)
        cyl("sprocket", 0.36, 0.3, (x, -3.1, 0.62), dg, axis="X", segments=10)
        cyl("idler", 0.33, 0.28, (x, 3.08, 0.58), st, axis="X", segments=12)
        for y in (-1.6, 0.2, 1.9):
            cyl("roller", 0.1, 0.2, (x, y, 0.95), st, axis="X", segments=8)

        # Track: upper run, lower run, wrap at both ends, with grousers on top.
        box("track_top", (0.62, 6.2, 0.1), (x, 0.0, 1.05), tr)
        box("track_bottom", (0.62, 5.4, 0.1), (x, 0.0, 0.05), tr)
        cyl("track_front", 0.52, 0.62, (x, 3.05, 0.55), tr, axis="X", segments=12)
        cyl("track_rear", 0.52, 0.62, (x, -3.05, 0.55), tr, axis="X", segments=12)
        for i in range(16):
            box("grouser", (0.64, 0.08, 0.04), (x, -2.9 + i * 0.39, 1.11), tr)

        # Side skirt with rubber flaps at the front, a team-colour stripe along it.
        box("skirt", (0.06, 6.0, 0.55), (side * 1.82, 0.1, 1.2), g, bevel=0.01)
        box("skirt_stripe", (0.07, 2.0, 0.14), (side * 1.83, -0.3, 1.25), team)
        for i in range(3):
            box("flap", (0.05, 0.42, 0.5), (side * 1.82, 2.4 + i * 0.44, 0.75), rb)
        # Stowage boxes on the fenders.
        for y in (-0.9, 0.4):
            box("stowage", (0.42, 1.1, 0.4), (side * 1.55, y, 1.7), dg, bevel=0.03)

    # Rear: two external fuel drums across the hull back.
    for x in (-0.75, 0.75):
        cyl("drum", 0.3, 1.2, (x, -3.6, 1.45), dg, axis="X", segments=14, bevel=0.03)
        for dx in (-0.4, 0.4):
            cyl("drum_band", 0.31, 0.04, (x + dx, -3.6, 1.45), st, axis="X", segments=14)

    # Turret: the T-90A welded turret, angular, low, with the Kontakt-5 "clamshell" wedges on the cheeks.
    turret = extrude("turret", [(-1.15, 0.85), (-0.42, 1.3), (0.42, 1.3), (1.15, 0.85), (1.22, -0.45), (0.95, -1.55),
                                (-0.95, -1.55), (-1.22, -0.45)], 0.6, (0, 0.3, 1.55), g, top_scale=0.86,
                     top_shift=(0, -0.08), bevel=0.03)
    turret.parent = hull
    cyl("turret_ring", 1.2, 0.12, (0, 0, -0.02), dg, segments=24, parent=turret)
    for side in (-1, 1):
        wedge = [(side * 0.4, 1.3), (side * 1.18, 0.82), (side * 1.25, 1.05), (side * 0.55, 1.9)]
        if side > 0:
            wedge.reverse()
        extrude("k5", wedge, 0.5, (0, 0, 0.05), g, top_scale=0.92, top_shift=(0, -0.12), parent=turret, bevel=0.02)
        for i in range(3):
            box("k5_seam", (0.03, 0.55, 0.02), (side * (0.55 + i * 0.22), 1.25 - i * 0.12, 0.56), dg, parent=turret)
        # Shtora dazzler boxes with the red IR lenses, and smoke dischargers along the turret side.
        box("shtora", (0.42, 0.36, 0.34), (side * 0.85, 1.45, 0.72), dg, bevel=0.03, parent=turret)
        box("shtora_lens", (0.3, 0.04, 0.24), (side * 0.85, 1.64, 0.72), lens, parent=turret)
        for i in range(6):
            cyl("smoke", 0.055, 0.3, (side * 1.12, 0.45 - i * 0.18, 0.62), dg, axis="Y",
                segments=8, parent=turret).rotation_euler = (0.6, 0, side * -0.4)
        # Stowage bins on the bustle sides.
        box("bin", (0.25, 0.9, 0.42), (side * 1.12, -1.0, 0.3), dg, bevel=0.03, parent=turret)
    box("roof_team", (0.7, 0.6, 0.03), (0.35, -0.75, 0.61), team, parent=turret)
    box("vent", (0.35, 0.35, 0.08), (-0.45, -0.95, 0.63), dg, parent=turret)

    # Gunner's sight block and commander's cupola with the Kord machine gun.
    box("sight", (0.45, 0.55, 0.4), (-0.55, 0.45, 0.78), dg, bevel=0.04, parent=turret)
    box("sight_glass", (0.32, 0.03, 0.22), (-0.55, 0.73, 0.83), glass, parent=turret)
    cup = cyl("cupola", 0.38, 0.22, (0.5, -0.15, 0.68), dg, segments=14, bevel=0.03, parent=turret)
    cyl("cupola_hatch", 0.3, 0.06, (0.5, -0.15, 0.82), g, segments=14, parent=turret)
    box("kord_mount", (0.12, 0.3, 0.28), (0.5, 0.2, 0.9), st, parent=turret)
    cyl("kord", 0.035, 1.3, (0.5, 0.7, 0.98), st, axis="Y", segments=8, parent=turret)
    box("kord_box", (0.18, 0.22, 0.18), (0.62, 0.2, 0.9), dg, parent=turret)
    box("snorkel", (0.2, 1.4, 0.2), (-0.6, -1.25, 0.7), dg, parent=turret)

    # Gun: mantlet, barrel with thermal sleeve sections and fume extractor.
    barrel = box("barrel", (0.55, 0.4, 0.45), (0, 1.4, 0.33), dg, bevel=0.05, parent=turret)
    cyl("gun_tube", 0.085, 5.6, (0, 2.9, 0), st, axis="Y", segments=12, parent=barrel)
    cyl("sleeve_1", 0.12, 1.6, (0, 1.2, 0), g, axis="Y", segments=12, parent=barrel)
    cyl("evacuator", 0.15, 0.55, (0, 2.6, 0), g, axis="Y", segments=12, parent=barrel)
    cyl("sleeve_2", 0.11, 1.5, (0, 3.75, 0), g, axis="Y", segments=12, parent=barrel)
    cyl("muzzle", 0.1, 0.2, (0, 5.6, 0), st, axis="Y", segments=12, parent=barrel)

    if wreck:
        # Knocked-out: turret blown off its ring and skewed, gun drooping, a scorched hole in the roof.
        turret.location = (0.5, 0.9, 1.62)
        turret.rotation_euler = (0.18, -0.25, 0.6)
        barrel.rotation_euler = (-0.15, 0, 0)
        sphere("scorch", 0.5, (0, 0.3, 1.56), mat("soot", (0.03, 0.03, 0.03)), scale=(1.6, 1.6, 0.1))
    return hull
