"""Ontology schema: entity types, relation types, geographic taxonomy, era periods."""

ENTITY_TYPES = {
    "agency": {
        "label": "Agentur",
        "color": "#c8a96e",
        "subtypes": ["full_service", "boutique", "network", "holding", "digital", "media", "direct"],
    },
    "person": {
        "label": "Person",
        "color": "#7eb8d4",
        "subtypes": ["creative_director", "copywriter", "art_director", "account", "strategist", "founder", "photographer"],
    },
    "era": {
        "label": "Epoche",
        "color": "#9b7ec8",
        "subtypes": ["decade", "movement", "period", "scene"],
    },
    "work": {
        "label": "Kampagne",
        "color": "#7ec87e",
        "subtypes": ["campaign", "ad", "jingle", "film", "print", "poster", "brand"],
    },
    "concept": {
        "label": "Konzept",
        "color": "#c87e7e",
        "subtypes": ["strategy", "methodology", "movement", "principle"],
    },
    "scandal": {
        "label": "Skandal",
        "color": "#d44444",
        "subtypes": ["ethical", "legal", "financial", "creative"],
    },
    "life": {
        "label": "Agenturleben",
        "color": "#d4a44c",
        "subtypes": ["culture", "role", "ritual", "hierarchy", "economics"],
    },
    "technology": {
        "label": "Technologie",
        "color": "#7ec8c8",
        "subtypes": ["print", "broadcast", "digital", "studio", "software"],
    },
    "visual": {
        "label": "Visuelles",
        "color": "#a0a0a0",
        "subtypes": ["photography", "illustration", "typography", "archive"],
    },
}

# Default entity type per KB category
CATEGORY_ENTITY_TYPE = {
    "agencies":   "agency",
    "people":     "person",
    "eras":       "era",
    "work":       "work",
    "philosophy": "concept",
    "scandals":   "scandal",
    "life":       "life",
    "technology": "technology",
    "visuals":    "visual",
}

RELATION_TYPES = {
    # Agency ↔ Person
    "founded_by":        {"label": "gegründet von",        "inverse": "founded"},
    "led_by":            {"label": "geleitet von",          "inverse": "led"},
    "employed":          {"label": "beschäftigte",          "inverse": "worked_at"},
    # Agency ↔ Agency
    "part_of":           {"label": "Teil von",              "inverse": "contains"},
    "spawned":           {"label": "hervorgegangen aus",    "inverse": "spawned_from"},
    "competed_with":     {"label": "konkurrierte mit",      "inverse": "competed_with"},
    "acquired":          {"label": "übernahm",              "inverse": "acquired_by"},
    "merged_with":       {"label": "fusionierte mit",       "inverse": "merged_with"},
    # ↔ Work
    "created":           {"label": "schuf",                 "inverse": "created_by"},
    "art_directed_by":   {"label": "Art-Direction von",     "inverse": "art_directed"},
    "written_by":        {"label": "Text von",              "inverse": "wrote"},
    # Person ↔ Person
    "influenced":        {"label": "beeinflusste",          "inverse": "influenced_by"},
    "mentored":          {"label": "mentorte",              "inverse": "mentored_by"},
    "collaborated_with": {"label": "arbeitete mit",         "inverse": "collaborated_with"},
    # ↔ Era / Concept
    "shaped_era":        {"label": "prägte",                "inverse": "shaped_by"},
    "belongs_to_era":    {"label": "gehört zu",             "inverse": "includes"},
    "exemplifies":       {"label": "verkörpert",            "inverse": "exemplified_by"},
    "created_concept":   {"label": "entwickelte",           "inverse": "developed_by"},
    "contradicts":       {"label": "widerspricht",          "inverse": "contradicted_by"},
    "evolved_from":      {"label": "entwickelte sich aus",  "inverse": "evolved_into"},
    # ↔ Scandal / Life
    "involved_in":       {"label": "beteiligt an",          "inverse": "involves"},
    "caused":            {"label": "verursachte",           "inverse": "caused_by"},
    "characteristic_of": {"label": "charakteristisch für",  "inverse": "characterized_by"},
    # Technology
    "replaced_by":       {"label": "abgelöst durch",        "inverse": "replaced"},
    "preceded_by":       {"label": "vorausgegangen durch",  "inverse": "preceded"},
    "used_by":           {"label": "verwendet von",         "inverse": "uses"},
    # Generic
    "related":           {"label": "verwandt mit",          "inverse": "related"},
    "worked_at":         {"label": "arbeitete bei",         "inverse": "employed"},
}

GEO_REGIONS = {
    "madison_avenue": {"label": "Madison Avenue / New York", "country": "US"},
    "chicago_school":  {"label": "Chicago",                   "country": "US"},
    "west_coast_us":   {"label": "Westküste USA",             "country": "US"},
    "soho_london":     {"label": "Soho / London",             "country": "GB"},
    "hamburg":         {"label": "Hamburg",                   "country": "DE"},
    "munich":          {"label": "München",                   "country": "DE"},
    "duesseldorf":     {"label": "Düsseldorf",                "country": "DE"},
    "frankfurt":       {"label": "Frankfurt",                 "country": "DE"},
    "berlin":          {"label": "Berlin",                    "country": "DE"},
    "zurich_basel":    {"label": "Zürich / Basel",            "country": "CH"},
    "vienna":          {"label": "Wien",                      "country": "AT"},
    "paris":           {"label": "Paris",                     "country": "FR"},
    "global":          {"label": "Global / International",    "country": None},
}

ERA_PERIODS = [
    {"id": "pre1950",  "label": "Vor 1950",  "from": None, "to": 1949},
    {"id": "1950s",    "label": "1950er",    "from": 1950, "to": 1959},
    {"id": "1960s",    "label": "1960er",    "from": 1960, "to": 1969},
    {"id": "1970s",    "label": "1970er",    "from": 1970, "to": 1979},
    {"id": "1980s",    "label": "1980er",    "from": 1980, "to": 1989},
    {"id": "1990s",    "label": "1990er",    "from": 1990, "to": 1999},
    {"id": "2000s",    "label": "2000er",    "from": 2000, "to": 2009},
    {"id": "2010s",    "label": "2010er",    "from": 2010, "to": 2019},
    {"id": "2020s",    "label": "2020er",    "from": 2020, "to": None},
]
