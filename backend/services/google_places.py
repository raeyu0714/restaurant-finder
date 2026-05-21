import httpx

GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

_FOOD_TYPES = {
    "restaurant", "cafe", "food", "bakery",
    "meal_delivery", "meal_takeaway", "bar", "ice_cream_shop",
}

_REVIEW_FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.formattedAddress,places.types,"
    "places.rating,places.userRatingCount,places.reviews"
)


def _extract_reviews(place: dict) -> tuple[float | None, int | None, list[str]]:
    """Pull rating, review_count and up to 5 review snippets from a Places API place dict."""
    rating       = place.get("rating")
    review_count = place.get("userRatingCount")
    reviews      = []
    for r in place.get("reviews", []):
        text = (r.get("text") or {}).get("text", "").strip()
        if text:
            reviews.append(text[:200])   # cap each snippet at 200 chars
    return rating, review_count, reviews


async def fetch_reviews(
    name: str,
    lat: float,
    lon: float,
    client: httpx.AsyncClient,
    api_key: str,
) -> tuple[float | None, int | None, list[str]]:
    """
    Fetches Google rating + up to 5 review texts for a Nominatim restaurant
    using a single searchText call.
    Returns (rating, review_count, reviews) — all None/[] on error.
    """
    if not api_key:
        return None, None, []
    try:
        payload = {
            "textQuery": name,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": 200.0,
                }
            },
            "languageCode": "zh-TW",
            "maxResultCount": 1,
        }
        r = await client.post(
            GOOGLE_PLACES_URL,
            json=payload,
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": _REVIEW_FIELD_MASK},
            timeout=10.0,
        )
        r.raise_for_status()
        places = r.json().get("places", [])
        if not places:
            return None, None, []
        return _extract_reviews(places[0])
    except Exception:
        return None, None, []


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
        "X-Goog-FieldMask": _REVIEW_FIELD_MASK,
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
        rating, review_count, reviews = _extract_reviews(place)
        results.append({
            "osm_type":     "google",
            "osm_id":       0,
            "name":         (place.get("displayName") or {}).get("text", ""),
            "lat":          loc.get("latitude", lat),
            "lon":          loc.get("longitude", lon),
            "address":      place.get("formattedAddress", ""),
            "_google_id":   place.get("id", ""),
            "_rating":      rating,
            "_review_count": review_count,
            "_reviews":     reviews,
        })

    return results
