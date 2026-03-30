from typing import Final

GEO_BASEMAP_DEFAULT_ID: Final = "openstreetmap"

GEO_BASEMAP_SPECS: dict[str, tuple[str | None, str | None, str | None]] = {
    "openstreetmap": ("OpenStreetMap", None, None),
    "carto_positron": ("CartoDB positron", None, None),
    "carto_dark": ("CartoDB dark_matter", None, None),
    "open_topo": (
        None,
        "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "© OpenStreetMap contributors, © OpenTopoMap",
    ),
    "esri_imagery": (
        None,
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "Tiles © Esri",
    ),
}

GEO_BASEMAP_MODEL_INSTRUCTIONS: Final = """
--- Basemap policy for geo_query_geo_projects (you choose; the backend only accepts canonical ids) ---

Parameter: basemap_id (optional string). Omit entirely when the user does not ask to change the map background,
so the previous basemap stays. When they do ask, you must pick exactly one of these ids (no free-form labels):

- openstreetmap — default street map; use for "standard", "streets", "OSM", or as a safe light neutral map.
- carto_positron — very light, minimal; use for "clearer", "lighter", "easier to read", "less busy", "white map".
- carto_dark — dark gray basemap; use for "dark", "night", "dark mode", "dark basemap".
- open_topo — shaded terrain / topography; use for "terrain", "topo", "topographic", "relief"; interpret typos
  like "terra" or "terain" as this when the user clearly means terrain, not satellite.
- esri_imagery — satellite / aerial; use for "satellite", "imagery", "aerial", "orthophoto".

Relative / contextual choices (use the active basemap_id from the latest [Map state] message in this turn):
- User wants clearer / brighter / easier to read:
  - If active is esri_imagery or open_topo → prefer carto_positron, or openstreetmap if they want more detail.
  - If active is carto_dark → prefer carto_positron or openstreetmap.
  - If already carto_positron or openstreetmap → keep carto_positron or openstreetmap unless they ask for something else.
- User wants darker / night → carto_dark.
- User wants satellite / aerial → esri_imagery.

Always infer intent from natural language; do not rely on the user knowing product names. Invalid or unknown ids
fall back to openstreetmap on the server, so you must pass a valid id from the list above.
""".strip()


def validate_basemap_id(basemap_id: str) -> str:
    if basemap_id in GEO_BASEMAP_SPECS:
        return basemap_id
    return GEO_BASEMAP_DEFAULT_ID
