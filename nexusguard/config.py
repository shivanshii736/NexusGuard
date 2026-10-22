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
STUDY_AREA_BBOX = None  # (north, south, east, west) to restrict to a few wards

GRAPH_CACHE = "data/processed/bengaluru.graphml"
