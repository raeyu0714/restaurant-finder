import asyncio
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT    = "RestaurantFinderApp/1.0 (course project)"

# For cuisine-specific intents, run these text queries FIRST
# (more precise than amenity=restaurant which returns everything)
CUISINE_TEXT_QUERIES: dict[str, list[str]] = {
    "japanese restaurant":  ["日本料理", "日式料理", "壽司", "拉麵", "居酒屋"],
    "korean restaurant":    ["韓式料理", "韓國料理", "韓式炸雞", "韓國烤肉"],
    "western restaurant":   ["西式料理", "美式料理", "pizza", "漢堡"],
    "hotpot restaurant":    ["火鍋", "麻辣鍋", "涮涮鍋", "鍋物"],
    "chinese restaurant":   ["港式飲茶", "港式點心", "中式料理", "中餐廳"],
    "asian restaurant":     ["越南料理", "泰式料理", "東南亞料理", "咖哩", "咖喱", "印度料理"],
    "italian restaurant":   ["義大利麵", "義式料理", "pasta"],
    "steak restaurant":     ["牛排", "牛排館", "steak"],
    "noodle restaurant":    ["拉麵", "牛肉麵", "麵館", "烏龍麵"],
    "rice restaurant":      ["炒飯", "雞腿飯", "排骨飯", "滷肉飯", "飯類", "便當"],
    "bubble tea shop":      ["手搖飲料", "珍珠奶茶", "奶茶店"],
    "dessert shop":         ["甜點", "蛋糕", "甜品", "冰淇淋", "剉冰", "芒果冰"],
    "fast food restaurant": ["麥當勞", "肯德基", "速食", "漢堡王"],
    "healthy restaurant":   ["健康餐廳", "沙拉", "輕食"],
    "vegetarian restaurant":["素食", "蔬食"],
    "cafe":                 ["咖啡廳", "咖啡店", "下午茶", "café"],
}

# OSM amenity tags (used as broader fallback after text queries)
FOOD_AMENITY_MAP: dict[str, list[str]] = {
    "fast food restaurant":  ["fast_food", "restaurant"],
    "cafe":                  ["cafe"],
    "breakfast cafe":        ["cafe", "restaurant"],
    "bubble tea shop":       ["cafe"],
    "dessert shop":          ["ice_cream", "cafe"],
    "italian restaurant":    ["restaurant"],
    "steak restaurant":      ["restaurant"],
    "rice restaurant":       ["restaurant"],
}

# Keywords for name-match scoring and strict filtering
FOOD_KEYWORD_MAP: dict[str, list[str]] = {
    "healthy restaurant":    ["健康", "輕食", "沙拉", "有機", "蔬食"],
    "vegetarian restaurant": ["素食", "蔬食", "vegetarian", "vegan", "齋"],
    "noodle restaurant":     ["麵", "拉麵", "烏龍", "蕎麥", "刀削", "河粉"],
    "fast food restaurant":  ["速食", "麥當勞", "肯德基", "漢堡", "炸雞", "麥", "KFC", "McDonald"],
    "restaurant":            ["餐廳", "飯館"],
    "japanese restaurant":   ["日式", "日本", "壽司", "拉麵", "丼", "居酒屋", "sushi", "ramen", "燒肉", "串燒", "抹茶", "天婦羅", "定食"],
    "taiwanese restaurant":  ["台式", "便當", "滷肉飯", "台灣", "熱炒", "小吃"],
    "breakfast cafe":        ["早餐", "早午餐", "蛋餅", "三明治", "brunch"],
    "cafe":                  ["咖啡", "café", "下午茶", "coffee"],
    "korean restaurant":     ["韓式", "韓國", "烤肉", "炸雞", "部隊鍋", "韓"],
    "western restaurant":    ["西式", "美式", "pizza", "漢堡", "義式"],
    "hotpot restaurant":     ["火鍋", "麻辣鍋", "涮涮鍋", "鍋", "shabu"],
    "chinese restaurant":    ["中式", "港式", "飲茶", "點心", "粵式"],
    "asian restaurant":      ["越南", "泰式", "東南亞", "pho", "thai", "咖哩", "curry", "印度"],
    "dessert shop":          ["甜點", "蛋糕", "冰淇淋", "甜品", "糕點", "布丁", "鬆餅", "剉冰", "霜淇淋", "芒果冰"],
    "bubble tea shop":       ["手搖", "珍珠奶茶", "奶茶", "飲料", "bubble tea", "茶飲"],
    "italian restaurant":    ["義大利", "pasta", "義式", "spaghetti", "pizza"],
    "steak restaurant":      ["牛排", "steak", "排餐"],
    "rice restaurant":       ["炒飯", "雞腿飯", "排骨飯", "飯", "便當", "米飯"],
    "restaurant":            ["餐廳", "飯店"],
}

# Cuisine-specific intents that require at least one keyword match in the name
CUISINE_SPECIFIC = {
    "japanese restaurant", "korean restaurant", "western restaurant",
    "hotpot restaurant", "chinese restaurant", "asian restaurant",
    "italian restaurant", "steak restaurant", "vegetarian restaurant",
    "bubble tea shop", "dessert shop", "rice restaurant",
}

# Hard exclusions: remove results whose name contains these words
EXCLUSION_MAP: dict[str, list[str]] = {
    "fast food restaurant":  ["素食", "蔬食", "vegetarian", "vegan", "健康蔬"],
    "healthy restaurant":    ["速食", "麥當勞", "肯德基", "KFC", "McDonald"],
    "vegetarian restaurant": ["烤肉", "牛排", "豬腳", "排骨"],
    "hotpot restaurant":     ["素食", "蔬食"],
    "dessert shop":          ["速食", "麥當勞", "肯德基", "火鍋"],
    "bubble tea shop":       ["速食", "麥當勞", "火鍋", "素食"],
    "japanese restaurant":   ["速食", "麥當勞", "肯德基", "早餐店", "豆漿"],
    "korean restaurant":     ["速食", "麥當勞", "早餐店", "豆漿"],
}


def _viewbox(lat: float, lon: float, radius_m: int) -> str:
    deg = radius_m / 111_000
    return f"{lon - deg},{lat + deg},{lon + deg},{lat - deg}"


async def _amenity_query(amenity, lat, lon, radius_m, client) -> list[dict]:
    params = {
        "amenity": amenity, "format": "jsonv2", "addressdetails": 1,
        "limit": 30, "viewbox": _viewbox(lat, lon, radius_m), "bounded": 1,
    }
    try:
        r = await client.get(NOMINATIM_URL, params=params,
                             headers={"User-Agent": USER_AGENT}, timeout=10.0)
        r.raise_for_status()
        await asyncio.sleep(1.1)
        return r.json()
    except Exception:
        return []


async def _text_query(query, lat, lon, radius_m, bounded, client) -> list[dict]:
    params = {
        "q": query, "format": "jsonv2", "addressdetails": 1,
        "limit": 30, "viewbox": _viewbox(lat, lon, radius_m), "bounded": bounded,
    }
    try:
        r = await client.get(NOMINATIM_URL, params=params,
                             headers={"User-Agent": USER_AGENT}, timeout=10.0)
        r.raise_for_status()
        await asyncio.sleep(1.1)
        return r.json()
    except Exception:
        return []


_FOOD_TYPES = {
    "restaurant", "cafe", "fast_food", "food_court", "bar", "pub",
    "ice_cream", "bakery", "confectionery", "deli", "butcher",
    "beverages", "convenience", "supermarket",
}

def _is_food_place(place: dict) -> bool:
    """Keep only results that are actual food/drink establishments."""
    cls  = place.get("class", "")
    typ  = place.get("type", "")
    return (cls == "amenity" and typ in _FOOD_TYPES) or \
           (cls == "shop"    and typ in {"bakery", "confectionery", "deli", "beverages"})


def _has_keyword(place: dict, keywords: list[str]) -> bool:
    name = (place.get("display_name") or "").lower()
    return any(kw.lower() in name for kw in keywords)


def _filter_by_intent(places: list[dict], food: str) -> list[dict]:
    bad_words = EXCLUSION_MAP.get(food, [])
    if not bad_words:
        return places
    return [p for p in places
            if not any(w.lower() in (p.get("display_name") or "").lower()
                       for w in bad_words)]


def _score_by_keywords(places: list[dict], food: str) -> list[dict]:
    keywords = FOOD_KEYWORD_MAP.get(food, [])
    if not keywords:
        return places

    def score(p: dict) -> int:
        name = (p.get("display_name") or "").lower()
        return sum(1 for kw in keywords if kw.lower() in name)

    return sorted(places, key=score, reverse=True)


def _strict_cuisine_filter(places: list[dict], food: str) -> list[dict]:
    """
    For cuisine-specific intents, only keep places whose name contains
    at least one matching keyword. Falls back to full list if too few match.
    """
    if food not in CUISINE_SPECIFIC:
        return places
    keywords = FOOD_KEYWORD_MAP.get(food, [])
    if not keywords:
        return places
    matched = [p for p in places if _has_keyword(p, keywords)]
    return matched if matched else places


async def search_restaurants(
    lat: float,
    lon: float,
    food: str,
    keywords: list[str],
    max_minutes: int,
    client: httpx.AsyncClient,
    raw_keyword: str | None = None,
) -> list[dict]:
    """
    Multi-strategy Nominatim search.

    Strategy:
      1. raw_keyword text query — the food word extracted directly from user input
         (e.g. "火鍋", "義大利麵", "燒烤") — works for ANY food type, not just predefined ones
      2. Cuisine-specific Chinese text queries (from CUISINE_TEXT_QUERIES)
      3. Amenity-tag queries (broader fallback)
      4. Generic restaurant search (last resort)

    # EXTENSION POINT: add user preferences (favourites boost, price range filter)
    """
    tight_r = max(max_minutes * 130, 900)
    wide_r  = tight_r * 2

    all_results: list[dict] = []

    # Strategy 1: raw food keyword from user text (always run when available)
    if raw_keyword:
        results = await _text_query(raw_keyword, lat, lon, tight_r, bounded=1, client=client)
        all_results.extend(results)

    # Strategy 2: cuisine-specific Chinese text queries (always run — raw keyword alone
    # is often too generic, e.g. "飲料" returns vending machines instead of drink shops)
    for term in CUISINE_TEXT_QUERIES.get(food, [])[:3]:
        if term == raw_keyword:
            continue
        results = await _text_query(term, lat, lon, tight_r, bounded=1, client=client)
        all_results.extend(results)
        if len(_deduplicate(all_results)) >= 15:
            break

    # Strategy 3: amenity-tag queries (fallback when few FOOD places found so far)
    # Count only food places — text searches sometimes return buildings that aren't food,
    # and we shouldn't skip amenity search just because non-food results exist.
    _food_so_far = [p for p in _deduplicate(all_results) if _is_food_place(p)]
    if len(_food_so_far) < 5 and not (raw_keyword and _food_so_far):
        for amenity in FOOD_AMENITY_MAP.get(food, ["restaurant"]):
            results = await _amenity_query(amenity, lat, lon, tight_r, client)
            all_results.extend(results)
            if len([p for p in _deduplicate(all_results) if _is_food_place(p)]) >= 5:
                break

    # Types that have their own OSM amenity (ice_cream, cafe) — don't flood with
    # generic restaurants when those amenities return nothing.
    _NO_GENERIC_FALLBACK = {"dessert shop", "bubble tea shop"}

    # Strategy 4: wider generic restaurant search
    _food_so_far = [p for p in _deduplicate(all_results) if _is_food_place(p)]
    if len(_food_so_far) < 3 and food not in _NO_GENERIC_FALLBACK:
        results = await _amenity_query("restaurant", lat, lon, wide_r, client)
        all_results.extend(results)

    # Strategy 5: last-resort unbounded text
    if not _deduplicate(all_results) and food not in _NO_GENERIC_FALLBACK:
        results = await _text_query("restaurant", lat, lon, wide_r, bounded=0, client=client)
        all_results.extend(results)

    deduped   = _deduplicate(all_results)
    # Remove buildings, shops, institutions.
    # For dessert/bubble tea, never fall back to non-food results (prevents buildings).
    # For other cuisines, fall back to deduped so we don't silently return nothing.
    food_only = [p for p in deduped if _is_food_place(p)]
    if food_only:
        base = food_only
    elif food in _NO_GENERIC_FALLBACK:
        base = []
    else:
        base = deduped

    excluded  = _filter_by_intent(base, food)
    base      = excluded if excluded else base

    # Apply cuisine-specific filter FIRST so we don't fall back to generic places
    # when doing the name-match step.  E.g. user wants ice cream → strict filter
    # drops unrelated restaurants → name-match then operates on dessert shops only.
    strict       = _strict_cuisine_filter(base, food)
    narrow_base  = strict if strict else base

    # If raw_keyword was provided, prefer results that contain it in the name.
    if raw_keyword:
        rk_matched = [p for p in narrow_base if raw_keyword in (p.get("display_name") or "")]
        narrow_base = rk_matched if rk_matched else narrow_base

    scored = _score_by_keywords(narrow_base, food)
    return scored


def _deduplicate(places: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in places:
        key = (p.get("osm_type"), p.get("osm_id"))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def parse_place(place: dict) -> dict:
    address = place.get("address", {})
    road    = address.get("road", address.get("pedestrian", address.get("neighbourhood", "")))
    city    = address.get("city", address.get("town", address.get("county", "")))
    addr_str = ", ".join(filter(None, [road, city])) or place.get("display_name", "")[:60]

    return {
        "osm_type": place.get("osm_type", "node"),
        "osm_id":   int(place.get("osm_id", 0)),
        "name":     place.get("display_name", "").split(",")[0].strip(),
        "lat":      float(place["lat"]),
        "lon":      float(place["lon"]),
        "address":  addr_str,
    }
