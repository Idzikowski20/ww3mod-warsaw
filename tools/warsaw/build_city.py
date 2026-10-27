"""Builds the Warsaw Srodmiescie map (a 2048 m square around PKiN) from GUGiK and OSM data.

Writes into the map folder:
  map.bin          256x256 playable cells (+1 border) of TEMPERAT terrain: Road where OSM has carriageway
  ground.png       2048x2048 ground texture, 1 m per pixel, in the Godot prototype's ground palette
  buildings.mesh   every LoD2 building as a triangle mesh plus the cells it blocks (format below)
  map.yaml         players, four spawns and one `warsawbuilding` actor per building
  map.png          lobby preview

Sources (data dir = game-studio/data/raw): Modele_3D/*.gml (GUGiK CityGML 2.0 LoD2, EPSG:2180),
wide_ground_osm.json (Overpass ways with inline geometry), wide_master_ortho.png (GUGiK ortho of the
5200 m window E 634400..639600, N 484400..489600, used for roof colours). Colours, widths and the
roof sampling copy game-studio/src/map/{district_loader,osm_ground}.gd.

buildings.mesh, little endian:
  "WMSH" u32 version=1 u32 buildingCount
  per building: u32 vertexCount, u32 cellCount, cellCount x (u16 x, u16 y) map cells,
                vertexCount x (f32 x, y, z, nx, ny, nz, r, g, b)
  Positions are world px in the camera frame (Camera3D.cs): x east, y up, z south; 24 px per 8 m cell.

Usage: python build_city.py <data dir> <map dir>
"""
import json
import math
import os
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

# --- Map frame -------------------------------------------------------------------------------
PKIN_E, PKIN_N = 636963.0, 486976.0
CELLS = 256                      # playable cells per side
METRES_PER_CELL = 8.0
TILE_PX = 24                     # mod.yaml MapGrid TileSize
PX_PER_M = TILE_PX / METRES_PER_CELL
SIZE_M = CELLS * METRES_PER_CELL
E_MIN, N_MAX = PKIN_E - SIZE_M / 2, PKIN_N + SIZE_M / 2
BORDER = 1                       # one unplayable cell around the map (Bounds: 1,1,256,256)

# --- Colours (district_loader.gd / osm_ground.gd) --------------------------------------------
BUILDING = (0.80, 0.76, 0.70)
FACADES = [(0.80, 0.76, 0.70), (0.74, 0.70, 0.64), (0.85, 0.82, 0.76), (0.68, 0.62, 0.55),
           (0.78, 0.72, 0.60), (0.64, 0.61, 0.58)]
GREEN_ROOF = (0.42, 0.48, 0.27)
ROOF_DESATURATE, ROOF_DARKEN, GREEN_MARGIN = 0.45, 0.06, 0.03
PKIN_RADIUS = 175.0
PKIN_STONE, PKIN_FLAT, PKIN_COPPER, PKIN_GOLD = (0.63, 0.59, 0.52), (0.40, 0.38, 0.36), (0.36, 0.56, 0.47), (0.80, 0.66, 0.30)
PKIN_COPPER_FROM, PKIN_GOLD_FROM = 180.0, 186.0

GROUND = (0.45, 0.43, 0.40)
ASPHALT, FOOT, CYCLE = (0.18, 0.18, 0.20), (0.50, 0.48, 0.46), (0.45, 0.22, 0.20)
GREEN, WATER, PARKING, PLATFORM, BARE = (0.27, 0.37, 0.19), (0.22, 0.34, 0.45), (0.42, 0.41, 0.40), (0.58, 0.56, 0.52), (0.55, 0.45, 0.34)

ORTHO_E0, ORTHO_N1, ORTHO_SIZE = 634400.0, 489600.0, 5200.0

# --- TEMPERAT tiles (verified in the earlier generator) ---------------------------------------
CLEAR, ROAD_TILES = 255, (227, 228)


def rgb8(c):
    return tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in c)


# --- EPSG:2180 (PL-1992) forward transverse Mercator, GRS80 -----------------------------------
def to_2180(lat, lon):
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0, lon0, fe, fn = 0.9993, math.radians(19.0), 500000.0, -5300000.0
    phi, lam = math.radians(lat), math.radians(lon)
    s, c = math.sin(phi), math.cos(phi)
    n = a / math.sqrt(1 - e2 * s * s)
    t = math.tan(phi) ** 2
    cc = ep2 * c * c
    aa = (lam - lon0) * c
    e4, e6 = e2 * e2, e2 * e2 * e2
    m = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
             - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
             + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
             - (35 * e6 / 3072) * math.sin(6 * phi))
    east = fe + k0 * n * (aa + (1 - t + cc) * aa ** 3 / 6 + (5 - 18 * t + t * t + 72 * cc - 58 * ep2) * aa ** 5 / 120)
    north = fn + k0 * (m + n * math.tan(phi) * (aa * aa / 2 + (5 - t + 9 * cc + 4 * cc * cc) * aa ** 4 / 24
                                                 + (61 - 58 * t + t * t + 600 * cc - 330 * ep2) * aa ** 6 / 720))
    return east, north


# --- Geometry ---------------------------------------------------------------------------------
def newell(ring):
    """Unit normal of a planar ring (right-handed: CCW seen from the normal side); None if degenerate."""
    nx = ny = nz = 0.0
    px, py, pz = ring[-1]
    for x, y, z in ring:
        nx += (py - y) * (pz + z)
        ny += (pz - z) * (px + x)
        nz += (px - x) * (py + y)
        px, py, pz = x, y, z
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-9:
        return None
    return nx / length, ny / length, nz / length


def triangulate(ring, normal):
    """Ear-clips a planar 3D ring projected on its own plane; triangle index triples. Fan if clipping fails."""
    nx, ny, nz = normal
    up = (0.0, 1.0, 0.0) if abs(ny) < 0.99 else (1.0, 0.0, 0.0)
    u = (up[1] * nz - up[2] * ny, up[2] * nx - up[0] * nz, up[0] * ny - up[1] * nx)
    ul = math.sqrt(sum(v * v for v in u))
    u = tuple(v / ul for v in u)
    v = (ny * u[2] - nz * u[1], nz * u[0] - nx * u[2], nx * u[1] - ny * u[0])
    pts = [(p[0] * u[0] + p[1] * u[1] + p[2] * u[2], p[0] * v[0] + p[1] * v[1] + p[2] * v[2]) for p in ring]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    idx = list(range(len(pts)))
    area = sum(pts[idx[i]][0] * pts[idx[(i + 1) % len(idx)]][1] - pts[idx[(i + 1) % len(idx)]][0] * pts[idx[i]][1]
               for i in range(len(idx)))
    if area < 0:
        idx.reverse()

    tris = []
    guard = 0
    while len(idx) > 3 and guard < 4 * len(pts) * len(pts):
        guard += 1
        clipped = False
        for i in range(len(idx)):
            a, b, c = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            if cross(pts[a], pts[b], pts[c]) <= 1e-9:
                continue
            inside = False
            for k in idx:
                if k in (a, b, c):
                    continue
                p = pts[k]
                if cross(pts[a], pts[b], p) >= 0 and cross(pts[b], pts[c], p) >= 0 and cross(pts[c], pts[a], p) >= 0:
                    inside = True
                    break
            if inside:
                continue
            tris.append((a, b, c))
            idx.pop(i)
            clipped = True
            break
        if not clipped:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    elif len(idx) > 3:
        tris.extend((idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1))
    return tris


# --- CityGML ------------------------------------------------------------------------------------
def parse_gml(path):
    """Yields buildings as lists of exterior rings, each a list of (E, N, Z) without the closing vertex."""
    rings, depth = [], 0
    for event, el in ET.iterparse(path, events=("start", "end")):
        tag = el.tag.rsplit("}", 1)[-1]
        if event == "start":
            if tag == "Building":
                depth += 1
            continue
        if tag == "exterior" and depth > 0:
            # Polygon exteriors only: a Solid's exterior wraps whole surfaces, not one ring.
            if not any(c.tag.endswith("LinearRing") for c in el):
                continue
            coords = []
            for p in el.iter():
                t = p.tag.rsplit("}", 1)[-1]
                if t in ("pos", "posList") and p.text:
                    coords.extend(float(x) for x in p.text.split())
            ring = [tuple(coords[i:i + 3]) for i in range(0, len(coords) - 2, 3)]
            if len(ring) > 3 and ring[0] == ring[-1]:
                ring.pop()
            if len(ring) >= 3:
                rings.append(ring)
            el.clear()
        elif tag == "Building":
            depth -= 1
            if depth == 0:
                if rings:
                    yield rings
                rings = []
                el.clear()


class Ortho:
    def __init__(self, path):
        self.img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
        self.h, self.w = self.img.shape[:2]

    def roof(self, e, n):
        """5x5 ortho average around a roof point, skipping dark gaps and blown highlights (district_loader.gd)."""
        px = int(min(max((e - ORTHO_E0) / ORTHO_SIZE, 0), 1) * (self.w - 1))
        py = int(min(max((ORTHO_N1 - n) / ORTHO_SIZE, 0), 1) * (self.h - 1))
        block = self.img[max(py - 2, 0):py + 3, max(px - 2, 0):px + 3].reshape(-1, 3)
        lum = block @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        block = block[(lum >= 0.06) & (lum <= 0.97)]
        if len(block) == 0:
            return BUILDING
        r, g, b = block.mean(axis=0)
        if g > r + GREEN_MARGIN and g > b + GREEN_MARGIN:
            return GREEN_ROOF
        grey = r * 0.299 + g * 0.587 + b * 0.114
        r, g, b = (x + (grey - x) * ROOF_DESATURATE for x in (r, g, b))
        return tuple(x * (1 - ROOF_DARKEN) for x in (r, g, b))


def pkin_colour(ring_avg_h, n):
    if ring_avg_h >= PKIN_GOLD_FROM:
        return PKIN_GOLD
    if abs(n[1]) < 0.3:
        return PKIN_STONE
    if n[1] < 0.95 and ring_avg_h >= PKIN_COPPER_FROM:
        return PKIN_COPPER
    return PKIN_FLAT


def to_px(e, n):
    """EPSG:2180 metres to world px (x east, z south), border included."""
    return (BORDER * TILE_PX + (e - E_MIN) * PX_PER_M, BORDER * TILE_PX + (N_MAX - n) * PX_PER_M)


def build_buildings(data_dir, ortho):
    buildings = []
    tiles = sorted(f for f in os.listdir(os.path.join(data_dir, "Modele_3D")) if f.endswith(".gml"))
    for name in tiles:
        kept = 0
        try:
            for rings in parse_gml(os.path.join(data_dir, "Modele_3D", name)):
                allv = [v for r in rings for v in r]
                ce = sum(v[0] for v in allv) / len(allv)
                cn = sum(v[1] for v in allv) / len(allv)
                if not (E_MIN <= ce < E_MIN + SIZE_M and N_MAX - SIZE_M < cn <= N_MAX):
                    continue
                buildings.append((ce, cn, rings))
                kept += 1
        except ET.ParseError as ex:
            print(f"  {name}: unreadable ({ex}), skipped", flush=True)
            continue
        print(f"  {name}: {kept} buildings in the map square", flush=True)

    out = []
    for i, (ce, cn, rings) in enumerate(buildings):
        base = min(v[2] for r in rings for v in r)
        is_pkin = math.hypot(ce - PKIN_E, cn - PKIN_N) < PKIN_RADIUS
        facade = FACADES[int(abs(math.sin(ce * 12.9898 + cn * 78.233) * 43758.5453)) % len(FACADES)]
        verts = []
        flat_rings = []
        for ring in rings:
            g = [(*to_px(e, n),) for e, n, _ in ring]
            gr = [(g[k][0], (ring[k][2] - base) * PX_PER_M, g[k][1]) for k in range(len(ring))]
            nrm = newell(gr)
            if nrm is None:
                continue
            if is_pkin:
                col = pkin_colour(sum(v[2] for v in ring) / len(ring) - base, nrm)
            elif nrm[1] > 0.3:
                col = ortho.roof(sum(v[0] for v in ring) / len(ring), sum(v[1] for v in ring) / len(ring))
            else:
                col = facade
            for a, b, c in triangulate(gr, nrm):
                for k in (a, b, c):
                    verts.append((*gr[k], *nrm, *col))
            if abs(nrm[1]) > 0.3:
                flat_rings.append([(x, z) for x, _, z in gr])
        if verts:
            out.append({"centre": to_px(ce, cn), "verts": verts, "flat": flat_rings, "pkin": is_pkin})
    return out


def footprints(buildings):
    """Map cells each building blocks: cells whose centre its roof/ground polygons cover, each cell owned once.
    Bigger buildings claim first; a building that ends up with no cell keeps the cell under its centre if free."""
    owner = np.full((CELLS + 2 * BORDER, CELLS + 2 * BORDER), -1, dtype=np.int32)
    order = sorted(range(len(buildings)), key=lambda i: -len(buildings[i]["verts"]))
    for i in order:
        b = buildings[i]
        xs = [p[0] for r in b["flat"] for p in r] or [b["centre"][0]]
        zs = [p[1] for r in b["flat"] for p in r] or [b["centre"][1]]
        x0, z0 = int(min(xs) // TILE_PX), int(min(zs) // TILE_PX)
        x1, z1 = int(max(xs) // TILE_PX) + 1, int(max(zs) // TILE_PX) + 1
        w, h = x1 - x0, z1 - z0
        mask = Image.new("1", (w * 4, h * 4), 0)
        draw = ImageDraw.Draw(mask)
        for r in b["flat"]:
            if len(r) >= 3:
                draw.polygon([((x / TILE_PX - x0) * 4, (z / TILE_PX - z0) * 4) for x, z in r], fill=1)
        m = np.asarray(mask, dtype=bool)
        cells = []
        for cz in range(h):
            for cx in range(w):
                mx, mz = x0 + cx, z0 + cz
                if not (BORDER <= mx < CELLS + BORDER and BORDER <= mz < CELLS + BORDER):
                    continue
                if m[cz * 4 + 2, cx * 4 + 2] and owner[mz, mx] < 0:
                    owner[mz, mx] = i
                    cells.append((mx, mz))
        if not cells:
            mx, mz = int(b["centre"][0] // TILE_PX), int(b["centre"][1] // TILE_PX)
            if BORDER <= mx < CELLS + BORDER and BORDER <= mz < CELLS + BORDER and owner[mz, mx] < 0:
                owner[mz, mx] = i
                cells.append((mx, mz))
        b["cells"] = cells
    return owner


# --- OSM ground ---------------------------------------------------------------------------------
def road_width(tags):
    hw = tags.get("highway", "")
    base = {"motorway": 12, "trunk": 12, "primary": 12, "motorway_link": 12, "trunk_link": 12, "primary_link": 12,
            "secondary": 9, "secondary_link": 9, "tertiary": 7, "tertiary_link": 7,
            "footway": 2, "path": 2, "steps": 2, "pedestrian": 2, "corridor": 2, "cycleway": 2,
            "proposed": 0, "construction": 0, "elevator": 0, "platform": 0}.get(hw, 5)
    if base <= 0 or tags.get("footway") == "crossing":
        return 0.0
    try:
        tagged = float(tags.get("width", "").replace(",", "."))
        if 1.0 <= tagged <= 60.0:
            return tagged
    except ValueError:
        pass
    drivable = hw not in ("footway", "path", "steps", "pedestrian", "corridor", "cycleway", "track", "raceway")
    try:
        lanes = int(tags.get("lanes", "0"))
    except ValueError:
        lanes = 0
    if drivable and lanes > 0:
        return lanes * 3.25
    return float(base)


FOOT_CLASSES = ("footway", "pedestrian", "path", "steps", "corridor")
GREEN_LEISURE = ("park", "garden", "pitch", "dog_park")
GREEN_LANDUSE = ("grass", "forest", "recreation_ground", "meadow", "village_green")
GREEN_NATURAL = ("wood", "scrub", "shrubbery")

# Class ids in the terrain raster that map.bin is derived from.
CLS_GROUND, CLS_ROAD = 0, 1


def build_ground(data_dir):
    size = int(SIZE_M)
    img = Image.new("RGB", (size, size), rgb8(GROUND))
    cls = Image.new("L", (size, size), CLS_GROUND)
    di, dc = ImageDraw.Draw(img), ImageDraw.Draw(cls)
    with open(os.path.join(data_dir, "wide_ground_osm.json"), encoding="utf-8") as f:
        ways = json.load(f)["elements"]

    def pts(w):
        out = []
        for g in w.get("geometry") or []:
            if g is None:
                continue
            e, n = to_2180(g["lat"], g["lon"])
            out.append((e - E_MIN, N_MAX - n))
        return out

    layers = {k: [] for k in ("water", "green", "bare", "parking", "paved_foot", "paved_road", "foot", "road", "cycle", "platform")}
    for w in ways:
        t = w.get("tags", {})
        p = pts(w)
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
        elif closed and t.get("amenity") == "parking":
            layers["parking"].append(p)
        elif closed and ("railway" in t or "public_transport" in t or hw == "platform") and t.get("railway") != "rail":
            layers["platform"].append(p)
        elif closed and ("area:highway" in t or (hw and t.get("area") == "yes")):
            kind = t.get("area:highway", hw)
            layers["paved_foot" if kind in FOOT_CLASSES else "paved_road"].append(p)
        elif hw:
            width = road_width(t)
            if width > 0:
                key = "cycle" if hw == "cycleway" else ("foot" if hw in FOOT_CLASSES else "road")
                layers[key].append((p, width))

    def polys(key, colour, c=None):
        for p in layers[key]:
            di.polygon(p, fill=rgb8(colour))
            if c is not None:
                dc.polygon(p, fill=c)

    def lines(key, colour, c=None):
        for p, width in layers[key]:
            wpx = max(1, int(round(width)))
            di.line(p, fill=rgb8(colour), width=wpx)
            if c is not None:
                dc.line(p, fill=c, width=wpx)
            r = width / 2
            for x, y in p:
                di.ellipse((x - r, y - r, x + r, y + r), fill=rgb8(colour))
                if c is not None:
                    dc.ellipse((x - r, y - r, x + r, y + r), fill=c)

    polys("water", WATER)
    polys("green", GREEN)
    polys("bare", BARE)
    polys("parking", PARKING)
    polys("paved_foot", FOOT)
    polys("paved_road", ASPHALT, CLS_ROAD)
    lines("foot", FOOT)
    lines("road", ASPHALT, CLS_ROAD)
    lines("cycle", CYCLE)
    polys("platform", PLATFORM)
    print("  ground:", {k: len(v) for k, v in layers.items()}, flush=True)
    return img, np.asarray(cls)


# --- Outputs ---------------------------------------------------------------------------------------
def write_mesh(path, buildings):
    with open(path, "wb") as f:
        f.write(b"WMSH")
        f.write(struct.pack("<II", 1, len(buildings)))
        for b in buildings:
            f.write(struct.pack("<II", len(b["verts"]), len(b["cells"])))
            for x, z in b["cells"]:
                f.write(struct.pack("<HH", x, z))
            f.write(np.asarray(b["verts"], dtype="<f4").tobytes())


def write_bin(path, cls):
    side = CELLS + 2 * BORDER
    # Road where a third of the cell is carriageway; everything else (pavement, parks, yards) is Clear.
    road = cls.reshape(CELLS, int(METRES_PER_CELL), CELLS, int(METRES_PER_CELL)).swapaxes(1, 2)
    road = (road == CLS_ROAD).mean(axis=(2, 3)) > 0.33
    with open(path, "wb") as f:
        f.write(struct.pack("<BHHIII", 2, side, side, 17, 0, 17 + 3 * side * side))
        for x in range(side):
            for y in range(side):
                inside = BORDER <= x < CELLS + BORDER and BORDER <= y < CELLS + BORDER
                if inside and road[y - BORDER, x - BORDER]:
                    f.write(struct.pack("<HB", ROAD_TILES[(x + y) & 1], 0))
                else:
                    f.write(struct.pack("<HB", CLEAR, (x * 7 + y * 13) % 16))
        f.write(b"\0" * (3 * side * side))


def find_spawn(owner, cx, cy, radius=4):
    """Nearest cell to (cx, cy) with a (2r+1)^2 square of unblocked cells around it."""
    side = owner.shape[0]
    best = None
    for d in range(0, 60):
        for y in range(cy - d, cy + d + 1):
            for x in range(cx - d, cx + d + 1):
                if max(abs(x - cx), abs(y - cy)) != d:
                    continue
                if not (BORDER + radius <= x < side - BORDER - radius and BORDER + radius <= y < side - BORDER - radius):
                    continue
                if (owner[y - radius:y + radius + 1, x - radius:x + radius + 1] < 0).all():
                    best = (x, y)
                    break
            if best:
                return best
    return (cx, cy)


HEADER = """MapFormat: 12

RequiresMod: ww3mod

Title: Warsaw Srodmiescie WW3

Author: Idzikowski20

Tileset: TEMPERAT

MapSize: {side},{side}

Bounds: {b},{b},{cells},{cells}

Visibility: Lobby

Categories: Conquest

Rules: rules.yaml

Players:
	PlayerReference@Neutral:
		Name: Neutral
		OwnsWorld: True
		NonCombatant: True
		Faction: Random
	PlayerReference@Creeps:
		Name: Creeps
		NonCombatant: True
		Faction: Random
		Enemies: Multi0, Multi1, Multi2, Multi3
"""


def write_yaml(path, buildings, owner):
    side = CELLS + 2 * BORDER
    lines = [HEADER.format(side=side, b=BORDER, cells=CELLS)]
    for k in range(4):
        lines.append(f"\tPlayerReference@Multi{k}:\n\t\tName: Multi{k}\n\t\tPlayable: True\n\t\tFaction: Random\n\t\tEnemies: Creeps\n")
    lines.append("\nActors:\n")
    n = 0
    for cx, cy in ((24, 24), (side - 25, 24), (24, side - 25), (side - 25, side - 25)):
        x, y = find_spawn(owner, cx, cy)
        lines.append(f"\tActor{n}: mpspawn\n\t\tOwner: Neutral\n\t\tLocation: {x},{y}\n")
        n += 1
    for i, b in enumerate(buildings):
        if not b["cells"]:
            continue
        x, y = b["cells"][0]
        lines.append(f"\tActor{n}: warsawbuilding\n\t\tOwner: Neutral\n\t\tLocation: {x},{y}\n\t\tCityBuilding: {i}\n")
        n += 1
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(lines))
    return n


def main():
    data_dir, map_dir = sys.argv[1], sys.argv[2]
    e, n = to_2180(52.2319, 21.0067)
    assert abs(e - 637000) < 300 and abs(n - 486900) < 300, (e, n)

    print("ground ...", flush=True)
    ground, cls = build_ground(data_dir)
    print("buildings ...", flush=True)
    ortho = Ortho(os.path.join(data_dir, "wide_master_ortho.png"))
    buildings = build_buildings(data_dir, ortho)
    owner = footprints(buildings)

    ground.save(os.path.join(map_dir, "ground.png"))
    write_mesh(os.path.join(map_dir, "buildings.mesh"), buildings)
    write_bin(os.path.join(map_dir, "map.bin"), cls)
    actors = write_yaml(os.path.join(map_dir, "map.yaml"), buildings, owner)

    preview = ground.resize((CELLS, CELLS), Image.BOX)
    px = preview.load()
    for b in buildings:
        for x, y in b["cells"]:
            px[x - BORDER, y - BORDER] = rgb8(BUILDING)
    preview.save(os.path.join(map_dir, "map.png"))

    verts = sum(len(b["verts"]) for b in buildings)
    blocked = int((owner >= 0).sum())
    print(f"done: {len(buildings)} buildings, {verts} vertices ({verts * 36 / 1e6:.1f} MB), "
          f"{blocked} blocked cells, {actors} actors", flush=True)


if __name__ == "__main__":
    main()
