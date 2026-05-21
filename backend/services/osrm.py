import httpx

OSRM_BASE = "https://router.project-osrm.org"

# OSRM uses longitude,latitude order (opposite of most conventions)
def _coord(lon: float, lat: float) -> str:
    return f"{lon},{lat}"


async def get_walking_times(
    origin_lat: float,
    origin_lon: float,
    destinations: list[tuple[float, float]],  # list of (lat, lon)
    client: httpx.AsyncClient,
) -> list[float]:
    """
    Calls OSRM Table service to get walking times (seconds) from origin to each destination.
    Returns list of minutes, one per destination. Returns 9999 on error for that leg.
    """
    if not destinations:
        return []

    # Build coordinate string: origin first, then all destinations
    coords = [_coord(origin_lon, origin_lat)] + [_coord(lon, lat) for lat, lon in destinations]
    coord_str = ";".join(coords)

    url = f"{OSRM_BASE}/table/v1/foot/{coord_str}"
    params = {"sources": "0", "annotations": "duration"}

    try:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        durations = data["durations"][0][1:]  # row 0 = from origin; skip col 0 (origin→origin)
        return [d / 60.0 if d is not None else 9999.0 for d in durations]
    except Exception:
        # Fallback: return 9999 so all candidates are filtered out gracefully
        return [9999.0] * len(destinations)


async def get_walking_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    client: httpx.AsyncClient,
) -> list[list[float]]:
    """
    Calls OSRM Route service for a single origin→destination pair.
    Returns a list of [lat, lon] coordinate pairs for Folium PolyLine.
    Returns a straight line as fallback.
    """
    coords = f"{_coord(origin_lon, origin_lat)};{_coord(dest_lon, dest_lat)}"
    url = f"{OSRM_BASE}/route/v1/foot/{coords}"
    params = {"overview": "full", "geometries": "geojson"}

    try:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        geojson_coords = data["routes"][0]["geometry"]["coordinates"]
        # OSRM returns [lon, lat]; Folium PolyLine expects [lat, lon]
        return [[c[1], c[0]] for c in geojson_coords]
    except Exception:
        # Straight-line fallback
        return [[origin_lat, origin_lon], [dest_lat, dest_lon]]
