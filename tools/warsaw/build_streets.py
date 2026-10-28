"""Streets of the 3D Warsaw map: OSM ground as layered 3D surfaces, kerbs, markings and street props.

A port of the Godot prototype's street layers (game-studio src/map/osm_ground.gd, street_props.gd,
tree_layer.gd, car_layer.gd) with realistic tiled surfaces and Blender-made props (blender_streets.py).

streets.mesh, little endian (read by CityMap.cs):
  "WSTR" u32 version=1
  u32 surfaceCount, surfaceCount x f32 tile size in metres            (atlas order = SURFACES)
  u32 groundVertexCount, vertices                                     (drawn in this order, no depth)
  u32 modelCount, per model: u32 vertexCount, vertices                (world px, origin at the model's foot)
  u32 instanceCount, per instance: u32 model, f32 x, z (world px), yaw (rad), scale, r, g, b
  Vertices are buildings.mesh's 12 floats. Ground: style 100 + surface (u, v = metres), or -2 plain colour.
  Models: style -3 = multiplied by the instance colour, -2 plain.

Shelters are real geometry with depth, so build() returns them as extra building-like meshes for
buildings.mesh (no actor, no footprint).
"""
import json
import math
import os
import random
import struct

import numpy as np

from build_city import (BORDER, CELLS, E_MIN, N_MAX, PX_PER_M, SIZE_M, TILE_PX, newell, road_width,
                        to_2180, to_px, triangulate)

SURFACES = ["asphalt", "slabs", "setts", "grass", "kerb", "cycle", "parking", "soil", "water"]
SURF = {n: i for i, n in enumerate(SURFACES)}
# Metres one surface tile covers; must match blender_streets.py SURFACES.
SURFACE_SIZE = {"asphalt": 4.0, "slabs": 2.0, "setts": 2.0, "grass": 4.0, "kerb": 1.0, "cycle": 4.0, "parking": 4.0,
                "soil": 4.0, "water": 8.0}
PROP_MODELS = ["lamp", "signal", "tree_lime", "tree_maple", "tree_conifer", "car_sedan", "car_hatch", "car_van", "car_small"]
PROP = {n: i for i, n in enumerate(PROP_MODELS)}

PAINT = (0.80, 0.78, 0.72)
RAIL = (0.30, 0.29, 0.28)
CYCLE_LANE_W, PARKING_LANE_W, LANE_W = 1.5, 2.2, 3.25
ZEBRA_STRIPE, ZEBRA_PITCH, ZEBRA_LEN, ZEBRA_SNAP = 0.5, 1.0, 4.0, 3.0
DASH_LEN, DASH_PERIOD, JUNCTION_CLEAR = 3.0, 8.0, 12.0
KERB_W, KERB_H, KERB_CLEAR = 0.25, 0.12, 9.0
TRAM_GAUGE, RAIL_W = 1.435, 0.25
SHELTER_H = 2.6
FOOT = ("footway", "pedestrian", "path", "steps", "corridor")
GREEN_LEISURE = ("park", "garden", "pitch", "dog_park")
GREEN_LANDUSE = ("grass", "forest", "recreation_ground", "meadow", "village_green")
GREEN_NATURAL = ("wood", "scrub", "shrubbery")
CAR_COLOURS = [(0.12, 0.12, 0.13), (0.22, 0.22, 0.24), (0.55, 0.56, 0.58), (0.78, 0.78, 0.76), (0.62, 0.15, 0.13),
               (0.16, 0.24, 0.42), (0.38, 0.38, 0.40), (0.85, 0.84, 0.80), (0.30, 0.34, 0.24)]
GREENS = ((0.17, 0.26, 0.12), (0.30, 0.38, 0.17))
ORIENT = {"parallel": (6.0, 0.0, 2.2), "diagonal": (3.6, math.pi / 4, 4.5), "perpendicular": (2.6, math.pi / 2, 5.0)}

LO = BORDER * TILE_PX
HI = LO + SIZE_M * PX_PER_M


def m(px):
    return px / PX_PER_M


def project(geom):
    return [to_px(*to_2180(g["lat"], g["lon"])) for g in geom if g]


def is_hidden(t):
    if t.get("tunnel", "no") != "no" or t.get("indoor") == "yes" or t.get("covered") == "yes":
        return True
    try:
        if int(t.get("layer", "0")) < 0 or float(t.get("level", "0").split(";")[0]) < 0:
            return True
    except ValueError:
        pass
    return False


def drivable(hw):
    return hw not in FOOT + ("cycleway", "proposed", "construction", "elevator", "platform", "track", "raceway", "")


def side_value(t, key, side):
    for k in (f"{key}:{side}", f"{key}:both"):
        if k in t:
            return t[k]
    return t.get(key, "") if key == "cycleway" else ""


def placement_shift(t, w):
    pl, lanes = t.get("placement", ""), t.get("lanes", "")
    try:
        lanes = int(lanes)
    except ValueError:
        return 0.0
    if lanes <= 0 or ":" not in pl:
        return 0.0
    kind, _, idx = pl.partition(":")
    try:
        i = int(idx)
    except ValueError:
        return 0.0
    if not 1 <= i <= lanes:
        return 0.0
    lw = w / lanes
    offsets = {"middle_of": lw / 2, "right_of": lw, "left_of": 0.0}
    if kind not in offsets:
        return 0.0
    return -(-w / 2 + (i - 1) * lw + offsets[kind])


# --- Clipping ---------------------------------------------------------------------------------------
def clip_poly(pts):
    """Sutherland-Hodgman against the map square (world px)."""
    def clip(poly, inside, cut):
        out = []
        for i in range(len(poly)):
            a, b = poly[i - 1], poly[i]
            if inside(b):
                if not inside(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside(a):
                out.append(cut(a, b))
        return out

    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))

    def at_z(z):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]), z)

    for inside, cut in ((lambda p: p[0] >= LO, at_x(LO)), (lambda p: p[0] <= HI, at_x(HI)),
                        (lambda p: p[1] >= LO, at_z(LO)), (lambda p: p[1] <= HI, at_z(HI))):
        pts = clip(pts, inside, cut)
        if len(pts) < 3:
            return []
    return pts


def clip_line(pts):
    """Splits a polyline into the runs that lie inside the map square (Liang-Barsky per segment)."""
    parts, cur = [], []
    for a, b in zip(pts, pts[1:]):
        t0, t1 = 0.0, 1.0
        dx, dz = b[0] - a[0], b[1] - a[1]
        ok = True
        for p, q in ((-dx, a[0] - LO), (dx, HI - a[0]), (-dz, a[1] - LO), (dz, HI - a[1])):
            if p == 0:
                if q < 0:
                    ok = False
                    break
                continue
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                ok = False
                break
        if not ok:
            if len(cur) >= 2:
                parts.append(cur)
            cur = []
            continue
        pa = (a[0] + dx * t0, a[1] + dz * t0)
        pb = (a[0] + dx * t1, a[1] + dz * t1)
        if not cur or cur[-1] != pa:
            if len(cur) >= 2:
                parts.append(cur)
            cur = [pa]
        cur.append(pb)
        if t1 < 1.0:
            parts.append(cur)
            cur = []
    if len(cur) >= 2:
        parts.append(cur)
    return parts


# --- Geometry writers ----------------------------------------------------------------------------
class Ground:
    """Ground triangles in draw order (painter's algorithm, bottom layer first)."""

    def __init__(self):
        self.v = []

    def tri(self, a, b, c, surface=None, colour=(1, 1, 1), y=0.0):
        style = 100.0 + SURF[surface] if surface else -2.0
        for x, z in (a, b, c):
            self.v.append((x, y * PX_PER_M, z, 0.0, 1.0, 0.0, *colour, m(x), m(z), style))

    def polygon(self, pts, surface=None, colour=(1, 1, 1), y=0.0):
        if len(pts) > 3 and pts[0] == pts[-1]:
            pts = pts[:-1]
        pts = clip_poly(pts)
        if len(pts) < 3:
            return
        ring = [(x, 0.0, z) for x, z in pts]
        for a, b, c in triangulate(ring, (0.0, 1.0, 0.0)):
            self.tri(pts[a], pts[b], pts[c], surface, colour, y)

    def quad(self, c, u, v, surface=None, colour=(1, 1, 1), y=0.0):
        p = [(c[0] - u[0] - v[0], c[1] - u[1] - v[1]), (c[0] + u[0] - v[0], c[1] + u[1] - v[1]),
             (c[0] + u[0] + v[0], c[1] + u[1] + v[1]), (c[0] - u[0] + v[0], c[1] - u[1] + v[1])]
        if not all(LO <= x <= HI and LO <= z <= HI for x, z in p):
            return
        self.tri(p[0], p[1], p[2], surface, colour, y)
        self.tri(p[0], p[2], p[3], surface, colour, y)

    def ribbon(self, line, width_m, surface=None, colour=(1, 1, 1), shift_m=0.0, y=0.0):
        """Mitred ribbon along a polyline (osm_ground.gd _add_ribbon), already clipped."""
        n = len(line)
        half, shift = width_m * PX_PER_M / 2, shift_m * PX_PER_M
        edges = []
        for i in range(n):
            if i == 0:
                d = (line[1][0] - line[0][0], line[1][1] - line[0][1])
            elif i == n - 1:
                d = (line[-1][0] - line[-2][0], line[-1][1] - line[-2][1])
            else:
                a = unit((line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]))
                b = unit((line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1]))
                d = (a[0] + b[0], a[1] + b[1])
            d = unit(d)
            side = (-d[1], d[0])
            p = line[i]
            edges.append(((p[0] + side[0] * (shift + half), p[1] + side[1] * (shift + half)),
                          (p[0] + side[0] * (shift - half), p[1] + side[1] * (shift - half))))
        for (l0, r0), (l1, r1) in zip(edges, edges[1:]):
            self.tri(l0, r0, l1, surface, colour, y)
            self.tri(r0, r1, l1, surface, colour, y)


def unit(d):
    length = math.hypot(*d)
    return (d[0] / length, d[1] / length) if length > 1e-9 else (1.0, 0.0)


# --- Layers --------------------------------------------------------------------------------------
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["elements"]


def ground_layers(data_dir):
    g = Ground()
    full = (CELLS + 2 * BORDER) * TILE_PX
    g.tri((0, 0), (full, 0), (full, full), "slabs")
    g.tri((0, 0), (full, full), (0, full), "slabs")

    layers = {k: [] for k in ("water", "green", "bare", "parking", "paved_foot", "paved_road", "platform",
                              "foot", "road", "cycle")}
    roads = []
    for w in load(os.path.join(data_dir, "wide_ground_osm.json")):
        t = w.get("tags", {})
        if is_hidden(t):
            continue
        p = project(w.get("geometry") or [])
        if len(p) < 2:
            continue
        closed = len(p) >= 4 and p[0] == p[-1]
        hw = t.get("highway", "")
        if closed and (t.get("natural") == "water" or "waterway" in t):
            layers["water"].append(p)
        elif closed and (t.get("leisure") in GREEN_LEISURE or t.get("landuse") in GREEN_LANDUSE or t.get("natural") in GREEN_NATURAL):
            layers["green"].append(p)
        elif closed and t.get("landuse") in ("construction", "brownfield") and "building" not in t and not hw:
            layers["bare"].append(p)
        elif closed and ("railway" in t or "public_transport" in t or hw == "platform") and t.get("railway") != "rail":
            layers["platform"].append(p)
        elif closed and ("area:highway" in t or (hw and t.get("area") == "yes")):
            layers["paved_foot" if t.get("area:highway", hw) in FOOT else "paved_road"].append(p)
        elif hw:
            width = road_width(t)
            if width <= 0:
                continue
            key = "cycle" if hw == "cycleway" else ("foot" if hw in FOOT else "road")
            layers[key].append((p, width, placement_shift(t, width), t))
            if key == "road":
                roads.append((p, width, placement_shift(t, width), t))

    for w in load(os.path.join(data_dir, "wide_trees_parking_osm.json")):
        t = w.get("tags", {})
        if w.get("type") == "way" and t.get("amenity") == "parking" and \
                t.get("parking", "") not in ("underground", "multi-storey", "rooftop"):
            p = project(w.get("geometry") or [])
            if len(p) >= 4:
                layers["parking"].append(p)

    for key, surface in (("water", "water"), ("green", "grass"), ("bare", "soil"), ("parking", "parking"),
                         ("paved_foot", "setts"), ("paved_road", "asphalt")):
        for p in layers[key]:
            g.polygon(p, surface)
    for p, width, shift, _ in layers["foot"]:
        for part in clip_line(p):
            g.ribbon(part, width, "setts", shift_m=shift)
    for p, width, shift, _ in layers["road"]:
        for part in clip_line(p):
            g.ribbon(part, width, "asphalt", shift_m=shift)
    for p, width, shift, _ in layers["cycle"]:
        for part in clip_line(p):
            g.ribbon(part, width, "cycle", shift_m=shift)
    for p in layers["platform"]:
        g.polygon(p, "setts", (1.12, 1.10, 1.06))
    counts = {k: len(v) for k, v in layers.items()}
    return g, roads, counts


def junctions(roads):
    """Vertices where three or more drivable edges meet (street_props.gd)."""
    uses = {}
    for p, *_ in roads:
        for i, q in enumerate(p):
            k = (round(q[0] * 10 / PX_PER_M), round(q[1] * 10 / PX_PER_M))
            uses[k] = uses.get(k, 0) + (1 if i in (0, len(p) - 1) else 2)
    pts = [(k[0] * PX_PER_M / 10, k[1] * PX_PER_M / 10) for k, n in uses.items() if n >= 3]
    return Hash(pts, 30 * PX_PER_M)


class Hash:
    def __init__(self, pts, cell):
        self.cell, self.grid = cell, {}
        for p in pts:
            self.grid.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(p)

    def near(self, p, r):
        cx, cz = int(p[0] // self.cell), int(p[1] // self.cell)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for q in self.grid.get((cx + dx, cz + dz), ()):
                    if math.hypot(q[0] - p[0], q[1] - p[1]) < r:
                        yield q


def markings(g, roads, junction_hash, data_dir):
    """Tram rails, lane dashes, cycle lanes, zebras and kerbs, painted over the roads in that order."""
    furniture = load(os.path.join(data_dir, "wide_furniture_osm.json"))
    for w in furniture:
        t = w.get("tags", {})
        if w.get("type") == "way" and t.get("railway") == "tram" and not is_hidden(t):
            for part in clip_line(project(w.get("geometry") or [])):
                g.ribbon(part, RAIL_W, None, RAIL, shift_m=TRAM_GAUGE / 2)
                g.ribbon(part, RAIL_W, None, RAIL, shift_m=-TRAM_GAUGE / 2)

    segments = Hash([], 20 * PX_PER_M)
    for p, width, shift, t in roads:
        lanes = t.get("lanes", "")
        lanes = int(lanes) if lanes.isdigit() else 0
        lo, hi, strips = -width / 2, width / 2, []
        for side, sgn in (("left", -1), ("right", 1)):
            edge = width / 2
            if side_value(t, "parking", side) == "lane":
                edge -= PARKING_LANE_W
            if side_value(t, "cycleway", side) == "lane":
                strips.append(sgn * (edge - CYCLE_LANE_W / 2))
                edge -= CYCLE_LANE_W
            if side == "left":
                lo = -edge
            else:
                hi = edge
        for part in clip_line(p):
            for off in strips:
                g.ribbon(part, CYCLE_LANE_W, "cycle", shift_m=off + shift)
            if lanes >= 2 and t.get("lane_markings") != "no":
                dashes(g, part, [shift + lo + (hi - lo) * k / lanes for k in range(1, lanes)], junction_hash)
            kerbs(g, part, width / 2, shift, junction_hash)
        for a, b in zip(p, p[1:]):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            segments.grid.setdefault((int(mid[0] // segments.cell), int(mid[1] // segments.cell)), []).append(
                (a, b, width / 2, shift))

    zebras = 0
    for w in furniture:
        t = w.get("tags", {})
        if w.get("type") != "node" or t.get("highway") != "crossing" or not marked(t):
            continue
        p = to_px(*to_2180(w["lat"], w["lon"]))
        hit = nearest_segment(segments, p, ZEBRA_SNAP * PX_PER_M)
        if hit:
            d, half_w, shift = hit
            side = (-d[1], d[0])
            centre = (p[0] + side[0] * shift * PX_PER_M, p[1] + side[1] * shift * PX_PER_M)
            zebra(g, centre, d, half_w)
            zebras += 1
    return segments, zebras


def marked(t):
    mk = t.get("crossing:markings", "")
    if mk:
        return "zebra" in mk or mk == "yes"
    return t.get("crossing", "") in ("zebra", "marked", "uncontrolled", "traffic_signals")


def nearest_segment(segments, p, limit):
    best, hit = limit, None
    cx, cz = int(p[0] // segments.cell), int(p[1] // segments.cell)
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            for a, b, half_w, shift in segments.grid.get((cx + dx, cz + dz), ()):
                ab = (b[0] - a[0], b[1] - a[1])
                l2 = ab[0] ** 2 + ab[1] ** 2
                if l2 < 1e-9:
                    continue
                k = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / l2))
                q = (a[0] + ab[0] * k, a[1] + ab[1] * k)
                dist = math.hypot(q[0] - p[0], q[1] - p[1])
                if dist < best:
                    best, hit = dist, (unit(ab), half_w, shift)
    return hit


def dashes(g, line, offsets, junction_hash):
    walked = 0.0
    for a, b in zip(line, line[1:]):
        length = m(math.hypot(b[0] - a[0], b[1] - a[1]))
        if length < 0.5:
            walked += length
            continue
        d = unit((b[0] - a[0], b[1] - a[1]))
        side = (-d[1], d[0])
        t = (-walked) % DASH_PERIOD
        while t + DASH_LEN <= length:
            mid = (a[0] + d[0] * (t + DASH_LEN / 2) * PX_PER_M, a[1] + d[1] * (t + DASH_LEN / 2) * PX_PER_M)
            if not any(True for _ in junction_hash.near(mid, JUNCTION_CLEAR * PX_PER_M)):
                for off in offsets:
                    c = (mid[0] + side[0] * off * PX_PER_M, mid[1] + side[1] * off * PX_PER_M)
                    g.quad(c, (d[0] * DASH_LEN / 2 * PX_PER_M, d[1] * DASH_LEN / 2 * PX_PER_M),
                           (side[0] * 0.08 * PX_PER_M, side[1] * 0.08 * PX_PER_M), None, PAINT)
            t += DASH_PERIOD
        walked += length


def zebra(g, p, d, half_w):
    side = (-d[1], d[0])
    t = -half_w + ZEBRA_PITCH / 2
    while t <= half_w - ZEBRA_STRIPE / 2:
        c = (p[0] + side[0] * t * PX_PER_M, p[1] + side[1] * t * PX_PER_M)
        g.quad(c, (d[0] * ZEBRA_LEN / 2 * PX_PER_M, d[1] * ZEBRA_LEN / 2 * PX_PER_M),
               (side[0] * ZEBRA_STRIPE / 2 * PX_PER_M, side[1] * ZEBRA_STRIPE / 2 * PX_PER_M), None, PAINT)
        t += ZEBRA_PITCH


def kerbs(g, line, half_w, shift, junction_hash):
    """Granite kerb strips along both carriageway edges, stopped short of junctions."""
    for a, b in zip(line, line[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1e-6:
            continue
        d = unit((b[0] - a[0], b[1] - a[1]))
        side = (-d[1], d[0])
        # Cut the junction discs out of this segment, then lay a strip on each remaining interval.
        # Junctions are always OSM vertices, so the ones that matter sit at a segment end.
        cuts = []
        for q in {*junction_hash.near(a, KERB_CLEAR * PX_PER_M), *junction_hash.near(b, KERB_CLEAR * PX_PER_M)}:
            along = (q[0] - a[0]) * d[0] + (q[1] - a[1]) * d[1]
            across = abs((q[0] - a[0]) * side[0] + (q[1] - a[1]) * side[1])
            r = KERB_CLEAR * PX_PER_M
            if across < r:
                h = math.sqrt(r * r - across * across)
                cuts.append((along - h, along + h))
        spans = [(0.0, length)]
        for c0, c1 in cuts:
            spans = [s for lo, hi in spans for s in ((lo, min(hi, c0)), (max(lo, c1), hi)) if s[1] - s[0] > 0.5 * PX_PER_M]
        for sgn in (-1, 1):
            off = (shift + sgn * (half_w + KERB_W / 2)) * PX_PER_M
            for lo, hi in spans:
                mid = (lo + hi) / 2
                c = (a[0] + d[0] * mid + side[0] * off, a[1] + d[1] * mid + side[1] * off)
                g.quad(c, (d[0] * (hi - lo) / 2, d[1] * (hi - lo) / 2),
                       (side[0] * KERB_W / 2 * PX_PER_M, side[1] * KERB_W / 2 * PX_PER_M), "kerb", y=KERB_H)


# --- Props ----------------------------------------------------------------------------------------
def props(data_dir, segments, owner):
    rnd = random.Random(20261027)
    out = []

    def free(p):
        cx, cz = int(p[0] // TILE_PX), int(p[1] // TILE_PX)
        return 0 <= cz < owner.shape[0] and 0 <= cx < owner.shape[1] and owner[cz, cx] < 0

    def inside(p):
        return LO <= p[0] <= HI and LO <= p[1] <= HI

    for w in load(os.path.join(data_dir, "wide_furniture_osm.json")):
        t = w.get("tags", {})
        if w.get("type") != "node":
            continue
        p = to_px(*to_2180(w["lat"], w["lon"]))
        if not inside(p):
            continue
        hw = t.get("highway")
        if hw == "street_lamp":
            hit = nearest_segment(segments, p, 20 * PX_PER_M)
            if hit:
                # Arm (+x in the model) towards the carriageway centre line.
                d = hit[0]
                side = (-d[1], d[0])
                a = segments_side(p, hit, segments)
                to_road = (side[0] * a, side[1] * a)
                yaw = math.atan2(-to_road[1], to_road[0])
            else:
                yaw = rnd.uniform(0, 2 * math.pi)
            out.append((PROP["lamp"], p, yaw, 1.0, (1, 1, 1)))
        elif hw == "traffic_signals":
            hit = nearest_segment(segments, p, 15 * PX_PER_M)
            if hit:
                d, half_w, shift = hit
                side = (-d[1], d[0])
                for sgn in (-1, 1):
                    off = (shift + sgn * (half_w + 1.0)) * PX_PER_M
                    q = (p[0] + side[0] * off, p[1] + side[1] * off)
                    # The heads face -z in the model; turn them towards the carriageway.
                    face = (-sgn * side[0], -sgn * side[1])
                    out.append((PROP["signal"], q, math.atan2(-face[0], -face[1]), 1.0, (1, 1, 1)))

    trees = []
    for w in load(os.path.join(data_dir, "wide_trees_parking_osm.json")):
        t = w.get("tags", {})
        if w.get("type") == "node" and t.get("natural") == "tree":
            trees.append(to_px(*to_2180(w["lat"], w["lon"])))
        elif w.get("type") == "way" and t.get("natural") == "tree_row":
            line = project(w.get("geometry") or [])
            carry = 0.0
            for a, b in zip(line, line[1:]):
                seg = math.hypot(b[0] - a[0], b[1] - a[1])
                d = unit((b[0] - a[0], b[1] - a[1]))
                k = 12 * PX_PER_M - carry
                while k <= seg:
                    trees.append((a[0] + d[0] * k, a[1] + d[1] * k))
                    k += 12 * PX_PER_M
                carry = (carry + seg) % (12 * PX_PER_M)
    for p in trees:
        if not inside(p) or not free(p):
            continue
        roll = rnd.random()
        model = "tree_conifer" if roll < 0.08 else ("tree_lime" if roll < 0.55 else "tree_maple")
        k = rnd.random()
        tint = tuple(GREENS[0][i] + (GREENS[1][i] - GREENS[0][i]) * k for i in range(3))
        out.append((PROP[model], p, rnd.uniform(0, 2 * math.pi), rnd.uniform(0.8, 1.35), tint))

    cars = []
    for w in load(os.path.join(data_dir, "wide_trees_parking_osm.json")):
        t = w.get("tags", {})
        if w.get("type") == "way" and t.get("amenity") == "parking" and \
                t.get("parking", "") not in ("underground", "multi-storey", "rooftop"):
            ring = project(w.get("geometry") or [])
            if len(ring) >= 4 and any(inside(q) for q in ring):
                fill_lot(ring, t.get("orientation", ""), rnd, cars)
    for w in load(os.path.join(data_dir, "wide_ground_osm.json")):
        t = w.get("tags", {})
        if "highway" not in t or is_hidden(t):
            continue
        width = road_width(t)
        line = project(w.get("geometry") or [])
        if len(line) < 2 or not any(inside(q) for q in line):
            continue
        for side, sgn in (("left", -1), ("right", 1)):
            k = kerb_parking(t, side)
            if k:
                line_kerb(line, width / 2, placement_shift(t, width), sgn, k, rnd, cars)
    for p, yaw in cars:
        if inside(p) and free(p):
            roll = rnd.random()
            model = "car_sedan" if roll < 0.35 else "car_hatch" if roll < 0.70 else "car_small" if roll < 0.85 else "car_van"
            out.append((PROP[model], p, yaw, 1.0, CAR_COLOURS[rnd.randrange(len(CAR_COLOURS))]))
    out.sort(key=lambda i: i[0])
    return out


def segments_side(p, hit, segments):
    """+1 if the road centre is on the +side of the nearest segment's direction from p, else -1."""
    d = hit[0]
    side = (-d[1], d[0])
    best, sign = 1e18, 1.0
    cx, cz = int(p[0] // segments.cell), int(p[1] // segments.cell)
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            for a, b, *_ in segments.grid.get((cx + dx, cz + dz), ()):
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                dist = math.hypot(mid[0] - p[0], mid[1] - p[1])
                if dist < best:
                    best = dist
                    sign = 1.0 if (mid[0] - p[0]) * side[0] + (mid[1] - p[1]) * side[1] > 0 else -1.0
    return sign


def point_in(p, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, zi = ring[i]
        xj, zj = ring[j]
        if (zi > p[1]) != (zj > p[1]) and p[0] < (xj - xi) * (p[1] - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def fill_lot(ring, orient, rnd, cars):
    """car_layer.gd _fill_lot: a bay grid along the lot's longest edge, cars kept fully inside."""
    best, d = 0.0, (1.0, 0.0)
    for a, b in zip(ring, ring[1:]):
        e = math.hypot(b[0] - a[0], b[1] - a[1])
        if e > best:
            best, d = e, unit((b[0] - a[0], b[1] - a[1]))
    n = (-d[1], d[0])
    us = [m(q[0] * d[0] + q[1] * d[1]) for q in ring]
    vs = [m(q[0] * n[0] + q[1] * n[1]) for q in ring]
    if orient not in ORIENT:
        orient = "parallel" if max(vs) - min(vs) < 4.0 else "perpendicular"
    axis, pitch, depth = n, 2.6, 5.4
    if orient == "parallel":
        axis, pitch, depth = d, 6.0, 2.4
    elif orient == "diagonal":
        axis, pitch, depth = unit((d[0] + n[0], d[1] + n[1])), 3.6, 4.5
    yaw = math.atan2(-axis[1], axis[0])
    row, v = 0, min(vs) + depth / 2
    while v < max(vs):
        u = min(us) + pitch / 2
        while u < max(us):
            c = ((d[0] * u + n[0] * v) * PX_PER_M, (d[1] * u + n[1] * v) * PX_PER_M)
            ends = [(c[0] + axis[0] * s * PX_PER_M, c[1] + axis[1] * s * PX_PER_M) for s in (-2.0, 2.0)]
            if point_in(c, ring) and all(point_in(e, ring) for e in ends) and rnd.random() < 0.72:
                cars.append((c, yaw + (math.pi if row % 2 else 0.0)))
            u += pitch
        row += 1
        v += depth + (6.0 if row % 2 == 0 and orient != "parallel" else 0.0)


def kerb_parking(t, side):
    pos = side_value(t, "parking", side)
    orient = ""
    if pos in ("lane", "street_side", "half_on_kerb", "on_kerb", "yes", "shoulder"):
        orient = t.get(f"parking:{side}:orientation", t.get("parking:both:orientation", ""))
    else:
        pos = ""
        for k in (f"parking:lane:{side}", "parking:lane:both"):
            if t.get(k) in ORIENT:
                orient, pos = t[k], "lane"
                for q in (f"{k}:{orient}", f"parking:lane:both:{orient}"):
                    if q in t:
                        pos = "lane" if t[q] == "on_street" else t[q]
                        break
                break
        if pos not in ("lane", "street_side", "half_on_kerb", "on_kerb", "painted_area_only"):
            return None
    return (pos, orient if orient in ORIENT else "parallel")


def line_kerb(line, half_w, shift, sgn, k, rnd, cars):
    pos, orient = k
    spacing, yaw_off, depth = ORIENT[orient]
    off = {"lane": half_w - depth / 2, "painted_area_only": half_w - depth / 2, "half_on_kerb": half_w}.get(pos, half_w + depth / 2)
    for a, b in zip(line, line[1:]):
        length = m(math.hypot(b[0] - a[0], b[1] - a[1]))
        if length < spacing:
            continue
        d = unit((b[0] - a[0], b[1] - a[1]))
        right = (-d[1], d[0])
        yaw = math.atan2(-d[1], d[0]) - yaw_off
        s = spacing / 2
        while s < length - spacing / 2:
            if rnd.random() < 0.6:
                c = (a[0] + (d[0] * s + right[0] * (shift + sgn * off)) * PX_PER_M,
                     a[1] + (d[1] * s + right[1] * (shift + sgn * off)) * PX_PER_M)
                cars.append((c, yaw))
            s += spacing


def shelters(data_dir):
    """Bus and tram shelters (amenity=shelter, shelter_type=public_transport footprints) as meshes."""
    out = []
    glass, roof = (0.42, 0.48, 0.50), (0.22, 0.24, 0.26)
    for w in load(os.path.join(data_dir, "wide_stops_osm.json")):
        t = w.get("tags", {})
        if w.get("type") != "way" or t.get("amenity") != "shelter":
            continue
        ring = project(w.get("geometry") or [])
        if len(ring) < 4 or not all(LO <= q[0] <= HI and LO <= q[1] <= HI for q in ring):
            continue
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        h, top = SHELTER_H * PX_PER_M, (SHELTER_H + 0.15) * PX_PER_M
        verts = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            quad = [(a[0], 0.0, a[1]), (b[0], 0.0, b[1]), (b[0], h, b[1]), (a[0], h, a[1])]
            n = newell(quad)
            if n is None:
                continue
            for i in (0, 1, 2, 0, 2, 3):
                verts.append((*quad[i], *n, *glass, 0.0, 0.0, -2.0))
        for y in (h, top):
            r3 = [(x, y, z) for x, z in ring]
            for a, b, c in triangulate(r3, (0.0, 1.0, 0.0)):
                for i in (a, b, c):
                    verts.append((*r3[i], 0.0, 1.0, 0.0, *roof, 0.0, 0.0, -2.0))
        out.append({"centre": ring[0], "verts": verts, "flat": [], "pkin": False, "cells": []})
    return out


def write(path, ground, models, instances, surface_sizes):
    with open(path, "wb") as f:
        f.write(b"WSTR")
        f.write(struct.pack("<II", 1, len(surface_sizes)))
        f.write(struct.pack(f"<{len(surface_sizes)}f", *surface_sizes))
        f.write(struct.pack("<I", len(ground.v)))
        f.write(np.asarray(ground.v, dtype="<f4").tobytes())
        f.write(struct.pack("<I", len(models)))
        for verts in models:
            f.write(struct.pack("<I", len(verts)))
            f.write(np.asarray(verts, dtype="<f4").tobytes())
        f.write(struct.pack("<I", len(instances)))
        for model, p, yaw, scale, tint in instances:
            f.write(struct.pack("<I7f", model, p[0], p[1], yaw, scale, *tint))


def load_models(props_json):
    """Blender props (metres, engine axes) to world px vertices; Tint materials get style -3."""
    with open(props_json) as f:
        raw = json.load(f)
    models = []
    for name in PROP_MODELS:
        verts = []
        for x, y, z, nx, ny, nz, r, g, b, tint in raw[name]:
            verts.append((x * PX_PER_M, y * PX_PER_M, z * PX_PER_M, nx, ny, nz, r, g, b, 0.0, 0.0, -3.0 if tint else -2.0))
        models.append(verts)
    return models
