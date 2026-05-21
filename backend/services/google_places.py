import httpx

GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

_FOOD_TYPES = {
    "restaurant", "cafe", "food", "bakery",
    "meal_delivery", "meal_takeaway", "bar", "ice_cream_shop",
}


async def search_places(
    query: str,
    lat: float,
    lon: float,
    radius_m: int,
    client: httpx.AsyncClient,
    api_key: str,
) -> list[dict]:
    """
    Calls Google Places API (New) v1 searchText.
    Returns place dicts in the same format as parse_place() output so main.py
    can treat Nominatim and Google results identically.
    Returns [] silently on any error or missing API key.
    """
    if not api_key:
        return []

    payload = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": float(radius_m),
            }
        },
        "languageCode": "zh-TW",
        "maxResultCount": 10,
    }
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.location,"
            "places.formattedAddress,places.types"
        ),
    }

    try:
        r = await client.post(GOOGLE_PLACES_URL, json=payload, headers=headers, timeout=10.0)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results: list[dict] = []
    for place in data.get("places", []):
        types = set(place.get("types", []))
        if not types.intersection(_FOOD_TYPES):
            continue
        loc = place.get("location", {})
        results.append({
            "osm_type": "google",
            "osm_id": 0,
            "name": (place.get("displayName") or {}).get("text", ""),
            "lat": loc.get("latitude", lat),
            "lon": loc.get("longitude", lon),
            "address": place.get("formattedAddress", ""),
            "_google_id": place.get("id", ""),
        })

    return results
