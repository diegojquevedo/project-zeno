"""
Lake County map constants (colors by projecttype).
From Project_to_analyze_Lake_County MainMap.constants.ts
"""
# [R, G, B] - border 100%, fill 60% opacity
PROJECT_TYPE_COLORS = {
    "319": [76, 175, 80],
    "Capital": [255, 235, 59],
    "Maintenance": [135, 206, 235],
    "Multiple Funding Sources": [218, 112, 214],
    "Other": [255, 152, 0],
    "SIRF": [138, 43, 226],
    "WMAG": [148, 112, 218],
    "WMB": [33, 150, 243],
}
DEFAULT_COLOR = [0, 255, 255]  # Unknown


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


FILL_OPACITY = 0.35


def get_style_by_projecttype(projecttype: str | None) -> dict:
    """Return folium GeoJson style: border and fill same color, border transparent like fill."""
    rgb = PROJECT_TYPE_COLORS.get(projecttype, DEFAULT_COLOR) if projecttype else DEFAULT_COLOR
    hex_color = _rgb_to_hex(rgb[0], rgb[1], rgb[2])
    return {
        "color": hex_color,
        "weight": 2,
        "opacity": FILL_OPACITY,
        "fillColor": hex_color,
        "fillOpacity": FILL_OPACITY,
    }
