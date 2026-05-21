"""
Folium map generator.
Builds an interactive Leaflet map (via Python folium) and returns it as an
HTML iframe string — ready to inject into the frontend page via innerHTML.
"""
import html as _html
import folium
from ..models.schemas import Restaurant, ParsedQuery

# Colour scheme
COLOR_USER       = "blue"
COLOR_RESTAURANT = "red"
ROUTE_COLOR      = "#2196F3"
ROUTE_WEIGHT     = 4


def build_map(
    user_lat: float,
    user_lon: float,
    restaurants: list[Restaurant],
    routes: dict[str, list[list[float]]],
    reasons: dict[str, str],
    parsed_query,           # ParsedQuery | None (None for basemap with no results)
    fav_ids: set[str] | None = None,
) -> str:
    """
    Creates a Folium map centred on the user's location.
    Adds user marker, restaurant markers, and walking route polylines.
    Returns `m._repr_html_()` — a self-contained <iframe srcdoc="..."> string
    that can be injected into the page via innerHTML.

    # EXTENSION POINT: highlight favourite restaurants with a star icon (gold colour)
    # EXTENSION POINT: add a heatmap layer showing user's past searches
    """
    m = folium.Map(
        location=[user_lat, user_lon],
        zoom_start=16,
        tiles="OpenStreetMap",
    )

    # User location marker
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup("📍 您的位置", max_width=150),
        tooltip="您的位置",
        icon=folium.Icon(color=COLOR_USER, icon="home", prefix="fa"),
    ).add_to(m)

    for restaurant in restaurants:
        reason = reasons.get(restaurant.id, "")
        walking = f"{restaurant.walking_minutes:.1f}"

        popup_html = (
            f"<div style='font-family:sans-serif;min-width:160px'>"
            f"<b>{restaurant.name}</b><br>"
            f"<small>{restaurant.address}</small><br>"
            f"🚶 步行約 <b>{walking} 分鐘</b>"
            f"</div>"
        )

        is_fav = fav_ids and restaurant.id in fav_ids
        marker_color = "orange" if is_fav else COLOR_RESTAURANT
        marker_icon  = "heart"  if is_fav else "cutlery"
        folium.Marker(
            location=[restaurant.latitude, restaurant.longitude],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{'❤️ ' if is_fav else ''}{restaurant.name} ({walking}分鐘)",
            icon=folium.Icon(color=marker_color, icon=marker_icon, prefix="fa"),
        ).add_to(m)

        # Walking route polyline
        route_coords = routes.get(restaurant.id, [])
        if route_coords:
            folium.PolyLine(
                locations=route_coords,
                color=ROUTE_COLOR,
                weight=ROUTE_WEIGHT,
                opacity=0.75,
                tooltip=f"步行路線 → {restaurant.name}",
            ).add_to(m)

    # Fit map to show all markers
    all_lats = [user_lat] + [r.latitude for r in restaurants]
    all_lons = [user_lon] + [r.longitude for r in restaurants]
    if restaurants:
        sw = [min(all_lats) - 0.003, min(all_lons) - 0.003]
        ne = [max(all_lats) + 0.003, max(all_lons) + 0.003]
        m.fit_bounds([sw, ne])

    # Use get_root().render() to get the full standalone HTML document,
    # then wrap it in an <iframe srcdoc> that we fully control.
    # This avoids Folium's aspect-ratio wrapper div (height:0;padding-bottom:60%)
    # which caused the map to render as a thin strip.
    standalone_html = m.get_root().render()
    escaped = _html.escape(standalone_html, quote=True)
    return f'<iframe srcdoc="{escaped}" style="width:100%;height:100%;border:none;display:block;"></iframe>'
