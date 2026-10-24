"""Tunable numbers. Everything marked ASSUMED must be labelled as such in the UI and deck."""

# Response-time targets (seconds). Fire: 3-5 min norm cited for Bengaluru. Others ASSUMED.
TARGETS_S = {"fire": 300, "ambulance": 600, "rescue": 900}  # ambulance/rescue ASSUMED

# ASSUMED peak-hour travel-time multipliers by OSM highway class (>=1.0 slows down).
PEAK_MULTIPLIERS = {
    "motorway": 1.3, "trunk": 1.8, "primary": 2.2, "secondary": 2.4,
    "tertiary": 2.6, "residential": 1.8, "unclassified": 2.0, "default": 2.0,
}

# Study area for the prototype: keep SMALL so the graph builds/caches in minutes.
STUDY_AREA_NAME = "Bengaluru, Karnataka, India"
# (north, south, east, west). ~5 km x 6 km of north-east Bengaluru around Hebbal.
STUDY_AREA_BBOX = (13.060, 13.015, 77.625, 77.570)

# ASSUMED free-flow speeds (km/h) used when OSM has no maxspeed tag (most Bengaluru roads).
FREEFLOW_SPEEDS_KMH = {
    "motorway": 60, "trunk": 50, "primary": 40, "secondary": 35, "tertiary": 30,
    "unclassified": 25, "residential": 25, "living_street": 15, "service": 15,
}
FREEFLOW_FALLBACK_KMH = 25

GRAPH_CACHE = "data/processed/bengaluru.graphml"


# ---- P1: assets, zones, caches -------------------------------------------------------------
# ASSUMED crews per base. Real vehicle counts are not public; label as assumption in UI/deck.
CREWS_DEFAULT = {"ambulance": 2, "fire": 2}

FIRE_CSV = "data/fire_stations.csv"             # hand-checked stations (id,name,lat,lon[,crews]); wins over OSM
ASSETS_CACHE = "data/processed/assets.json"     # committed to git (small) so teammates run offline
ZONES_CACHE = "data/processed/zones.json"
WARDS_FILE = "data/raw/wards.geojson"           # optional ward polygons; if absent -> grid cells
GRID_CELL_M = 1000                              # grid-cell fallback size

# Response-time targets in MINUTES; read by engine/settings.py (otherwise it defaults to 8/8/15).
RESPONSE_TARGETS_MIN = {"ambulance": 10, "fire": 5, "rescue": 15}