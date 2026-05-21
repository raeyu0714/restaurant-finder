"""
FastAPI backend for the Restaurant Finder application.

Endpoints:
  GET  /health       — liveness check
  GET  /public-key   — RSA public key PEM (for frontend signature verification)
  POST /login        — returns JWT access token
  POST /search       — full pipeline: NLP → Nominatim → OSRM → Folium → RSA sign
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from .config import get_settings, Settings
from .auth.jwt_handler import create_access_token, make_auth_dependency
from .crypto.signer import sign, verify, build_signed_data
from .models.schemas import SearchRequest, SearchResponse, ParsedQuery, Restaurant, FavouriteRequest
from .nlp.predictor import predict, models_exist
from .services import nominatim as nom_service
from .services import osrm as osrm_service
from .services import google_places as gp_service
from .services import favourites as fav_service
from .services.map_generator import build_map


# ── Lifespan: shared async HTTP client ───────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(timeout=20.0)
    if not models_exist():
        import warnings
        warnings.warn(
            "NLP models not found in backend/nlp/models/. "
            "Run: python -m backend.nlp.train  (from project root)",
            RuntimeWarning,
        )
    yield
    await app.state.http_client.aclose()


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Restaurant Finder API",
        version="1.0.0",
        description="自然語言餐廳查詢 API — NLP + Nominatim + OSRM + Folium",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    get_current_user = make_auth_dependency(settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)

    # ── GET /spin ────────────────────────────────────────────────────────────

    @app.get("/spin")
    async def spin_food(_user: dict = Depends(get_current_user)):
        import random
        from datetime import datetime, timezone, timedelta

        # All options pool
        all_options = [
            {"label": "拉麵",     "emoji": "🍜", "query": "我想吃拉麵"},
            {"label": "壽司",     "emoji": "🍣", "query": "我想吃壽司"},
            {"label": "火鍋",     "emoji": "🫕", "query": "我想吃火鍋"},
            {"label": "炸雞",     "emoji": "🍗", "query": "我想吃炸雞"},
            {"label": "牛排",     "emoji": "🥩", "query": "我想吃牛排"},
            {"label": "漢堡",     "emoji": "🍔", "query": "我想吃漢堡"},
            {"label": "披薩",     "emoji": "🍕", "query": "我想吃披薩"},
            {"label": "甜點",     "emoji": "🍰", "query": "附近的甜點店"},
            {"label": "咖啡廳",   "emoji": "☕",  "query": "附近的咖啡廳"},
            {"label": "韓式料理", "emoji": "🥘", "query": "我想吃韓式料理"},
            {"label": "台式便當", "emoji": "🍱", "query": "我想吃台式便當"},
            {"label": "早午餐",   "emoji": "🥞", "query": "附近的早午餐"},
            {"label": "珍珠奶茶", "emoji": "🧋", "query": "我想喝珍珠奶茶"},
            {"label": "義大利麵", "emoji": "🍝", "query": "我想吃義大利麵"},
            {"label": "烤肉",     "emoji": "🔥", "query": "我想吃烤肉"},
            {"label": "鍋貼",     "emoji": "🥟", "query": "我想吃鍋貼"},
        ]

        # Time-of-day weights (Taiwan time = UTC+8)
        tw_hour = (datetime.now(timezone.utc) + timedelta(hours=8)).hour

        if 6 <= tw_hour < 10:       # breakfast 06–10
            boosts = {"早午餐", "咖啡廳", "珍珠奶茶"}
        elif 10 <= tw_hour < 14:    # lunch 10–14
            boosts = {"拉麵", "台式便當", "壽司", "韓式料理", "義大利麵"}
        elif 14 <= tw_hour < 17:    # afternoon 14–17
            boosts = {"甜點", "咖啡廳", "珍珠奶茶"}
        elif 17 <= tw_hour < 21:    # dinner 17–21
            boosts = {"火鍋", "牛排", "烤肉", "炸雞", "披薩", "壽司"}
        else:                        # late night 21–06
            boosts = {"鍋貼", "拉麵", "炸雞", "漢堡", "珍珠奶茶"}

        # Boosted items appear 3× more often
        weighted = []
        for opt in all_options:
            weight = 3 if opt["label"] in boosts else 1
            weighted.extend([opt] * weight)

        chosen = random.choice(weighted)
        chosen["hint"] = _spin_time_hint(tw_hour)
        return chosen

    # ── GET /health ──────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        nlp_ready = models_exist()
        return {"status": "ok", "nlp_models_loaded": nlp_ready}

    # ── GET /public-key ──────────────────────────────────────────────────────

    @app.get("/public-key")
    async def get_public_key():
        return {"public_key_pem": settings.RSA_PUBLIC_KEY_PEM}

    # ── POST /login ──────────────────────────────────────────────────────────

    @app.post("/login")
    async def login(form_data: OAuth2PasswordRequestForm = Depends()):
        if (
            form_data.username != settings.DEMO_USERNAME
            or form_data.password != settings.DEMO_PASSWORD
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="帳號或密碼錯誤",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(
            secret_key=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
            data={"sub": form_data.username},
            expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        )
        return {"access_token": token, "token_type": "bearer"}

    # ── GET /basemap ─────────────────────────────────────────────────────────

    @app.get("/basemap")
    async def basemap(
        lat: float = get_settings().DEFAULT_LAT,
        lon: float = get_settings().DEFAULT_LON,
        _user: dict = Depends(get_current_user),
    ):
        """Returns a Folium base map centred on the user's location (no restaurant markers)."""
        m = build_map(
            user_lat=lat,
            user_lon=lon,
            restaurants=[],
            routes={},
            reasons={},
            parsed_query=None,
        )
        return {"map_html": m}

    # ── GET /favourites ──────────────────────────────────────────────────────

    @app.get("/favourites")
    async def get_favourites(user: dict = Depends(get_current_user)):
        return fav_service.get_favourites(user["sub"])

    # ── POST /favourites ─────────────────────────────────────────────────────

    @app.post("/favourites")
    async def add_favourite(
        req: FavouriteRequest,
        user: dict = Depends(get_current_user),
    ):
        favs = fav_service.add_favourite(user["sub"], req.model_dump())
        return favs

    # ── DELETE /favourites/{restaurant_id} ───────────────────────────────────

    @app.delete("/favourites/{restaurant_id:path}")
    async def remove_favourite(
        restaurant_id: str,
        user: dict = Depends(get_current_user),
    ):
        favs = fav_service.remove_favourite(user["sub"], restaurant_id)
        return favs

    # ── GET /favourites/map ──────────────────────────────────────────────────

    @app.get("/favourites/map")
    async def favourites_map(
        user: dict = Depends(get_current_user),
        fav_id: str | None = None,       # single favourite to highlight; None = show all
        lat: float = get_settings().DEFAULT_LAT,
        lon: float = get_settings().DEFAULT_LON,
    ):
        favs = fav_service.get_favourites(user["sub"])
        if not favs:
            return {"map_html": build_map(lat, lon, [], {}, {}, None)}

        display = [f for f in favs if f["id"] == fav_id] if fav_id else favs
        if not display:
            display = favs

        restaurants = [
            Restaurant(
                id=f["id"], name=f["name"],
                latitude=f["latitude"], longitude=f["longitude"],
                address=f["address"],
                walking_minutes=0, osm_type="node", osm_id=0,
            )
            for f in display
        ]
        fav_id_set = {r.id for r in restaurants}
        center_lat = display[0]["latitude"]
        center_lon = display[0]["longitude"]
        reasons    = {f["id"]: "❤️ 我的最愛" for f in display}

        map_html = build_map(
            user_lat=center_lat, user_lon=center_lon,
            restaurants=restaurants,
            routes={}, reasons=reasons,
            parsed_query=None,
            fav_ids=fav_id_set,
        )
        return {"map_html": map_html}

    # ── POST /search ─────────────────────────────────────────────────────────

    @app.post("/search", response_model=SearchResponse)
    async def search(
        req: SearchRequest,
        user: dict = Depends(get_current_user),
    ):
        settings = get_settings()
        client: httpx.AsyncClient = app.state.http_client

        # 1. NLP: parse natural language → structured query
        if not models_exist():
            raise HTTPException(
                status_code=503,
                detail="NLP 模型尚未就緒。請先執行: pip install sentence-transformers 然後 python -m backend.nlp.train",
            )
        nlp_result = predict(req.query)
        parsed = ParsedQuery(**nlp_result)

        # 2. Nominatim: search candidate restaurants
        raw_places = await nom_service.search_restaurants(
            lat=req.latitude,
            lon=req.longitude,
            food=parsed.food,
            keywords=parsed.keywords,
            max_minutes=parsed.time,
            client=client,
            raw_keyword=parsed.raw_keyword,
        )
        # Call Google Places only when user explicitly switches to Google mode
        if req.use_google and settings.GOOGLE_MAPS_API_KEY:
            radius_m = max(parsed.time * 130, 900)
            google_results = await gp_service.search_places(
                query=parsed.raw_keyword or parsed.food,
                lat=req.latitude,
                lon=req.longitude,
                radius_m=radius_m,
                client=client,
                api_key=settings.GOOGLE_MAPS_API_KEY,
            )
            raw_places = _merge_places(raw_places, google_results)

        if not raw_places:
            raise HTTPException(status_code=404, detail={
                "message": "找不到附近的餐廳，請嘗試其他關鍵字或擴大搜尋範圍。",
                "parsed_query": parsed.model_dump(),
            })

        places = [_parse_place(p) for p in raw_places]

        # 3. OSRM: get walking times for all candidates (batch)
        destinations = [(p["lat"], p["lon"]) for p in places]
        walking_minutes = await osrm_service.get_walking_times(
            req.latitude, req.longitude, destinations, client
        )

        # 4. Filter: keep only restaurants within the time limit
        filtered = [
            (place, wmin)
            for place, wmin in zip(places, walking_minutes)
            if wmin <= parsed.time
        ]
        if not filtered:
            raise HTTPException(status_code=404, detail={
                "message": f"步行 {parsed.time} 分鐘內找不到符合的餐廳。請嘗試增加時間或更換關鍵字。",
                "parsed_query": parsed.model_dump(),
            })

        # Fetch Google ratings + reviews concurrently for all filtered places
        review_tasks = []
        for place, _ in filtered:
            if place.get("_rating") is not None:
                # Already have rating from Google Places search result
                review_tasks.append(None)
            elif settings.GOOGLE_MAPS_API_KEY:
                # Nominatim result — fetch via searchText
                review_tasks.append(
                    gp_service.fetch_reviews(
                        name=place["name"],
                        lat=place["lat"],
                        lon=place["lon"],
                        client=client,
                        api_key=settings.GOOGLE_MAPS_API_KEY,
                    )
                )
            else:
                review_tasks.append(None)

        review_results = await asyncio.gather(*[t for t in review_tasks if t is not None])
        review_iter = iter(review_results)

        # Build Restaurant objects
        restaurants: list[Restaurant] = []
        for place, wmin in filtered:
            rid = place.get("_google_id") or f"{place['osm_type']}:{place['osm_id']}"
            if place.get("_rating") is not None:
                rating, review_count, reviews = place["_rating"], place["_review_count"], place["_reviews"]
            elif settings.GOOGLE_MAPS_API_KEY:
                rating, review_count, reviews = next(review_iter)
            else:
                rating, review_count, reviews = None, None, []

            restaurants.append(Restaurant(
                id=rid,
                name=place["name"],
                latitude=place["lat"],
                longitude=place["lon"],
                address=place["address"],
                walking_minutes=round(wmin, 1),
                osm_type=place["osm_type"],
                osm_id=place["osm_id"],
                rating=rating,
                review_count=review_count,
                reviews=reviews,
            ))

        # 5. Boost favourites to the top of the list
        # EXTENSION POINT: incorporate ratings or visit history for smarter ranking.
        user_favs = fav_service.get_favourites(user["sub"])
        if user_favs:
            fav_ids   = {f["id"] for f in user_favs}
            fav_names = {f["name"].lower() for f in user_favs}
            def _is_fav(r: Restaurant) -> bool:
                return r.id in fav_ids or r.name.lower() in fav_names
            restaurants = (
                [r for r in restaurants if _is_fav(r)] +
                [r for r in restaurants if not _is_fav(r)]
            )

        # 6. OSRM: fetch walking route GeoJSON for each filtered restaurant
        routes: dict[str, list[list[float]]] = {}
        route_tasks = [
            osrm_service.get_walking_route(
                req.latitude, req.longitude,
                r.latitude, r.longitude,
                client,
            )
            for r in restaurants
        ]
        route_results = await asyncio.gather(*route_tasks)
        for restaurant, route in zip(restaurants, route_results):
            routes[restaurant.id] = route

        # 6. Generate recommendation reasons (rule-based, 繁體中文)
        #    # EXTENSION POINT: replace with a fine-tuned language model or integrate
        #    user preferences (favourites, ratings) to personalise the reasons.
        reasons = _generate_reasons(restaurants, parsed)

        # 7. Build Folium map (Python Leaflet) → HTML iframe string
        fav_ids_in_results = [r.id for r in restaurants if fav_service.is_favourite(user["sub"], r.id)]
        map_html = build_map(
            user_lat=req.latitude,
            user_lon=req.longitude,
            restaurants=restaurants,
            routes=routes,
            reasons=reasons,
            parsed_query=parsed,
            fav_ids=set(fav_ids_in_results),
        )

        # 8. RSA-PSS SHA-256 digital signature
        timestamp  = datetime.now(timezone.utc).isoformat()
        signed_str = build_signed_data(restaurants, parsed, timestamp)
        signature  = sign(signed_str, settings.RSA_PRIVATE_KEY_PEM)

        # Sanity-check our own signature before returning
        if not verify(signed_str, signature, settings.RSA_PUBLIC_KEY_PEM):
            raise HTTPException(status_code=500, detail="內部錯誤：數位簽章驗證失敗")

        return SearchResponse(
            restaurants=restaurants,
            parsed_query=parsed,
            recommendation_reasons=reasons,
            favourite_ids=fav_ids_in_results,
            map_html=map_html,
            timestamp=timestamp,
            signature=signature,
            signed_data=signed_str,
        )

    return app


def _parse_place(p: dict) -> dict:
    """Wrapper: Google results already in parse_place() format; OSM results need conversion."""
    if p.get("osm_type") == "google":
        return p
    return nom_service.parse_place(p)


def _merge_places(nominatim: list[dict], google: list[dict]) -> list[dict]:
    """
    Append Google results that are not already represented by a Nominatim result.
    Two places are considered duplicates if they are within 50 m of each other.
    Nominatim results (raw OSM dicts) come first; Google results are pre-parsed dicts.
    """
    import math

    def _dist(a: dict, b: dict) -> float:
        dlat = (float(a["lat"]) - float(b["lat"])) * 111_000
        dlon = (float(a["lon"]) - float(b["lon"])) * 111_000 * math.cos(math.radians(float(a["lat"])))
        return math.sqrt(dlat ** 2 + dlon ** 2)

    nom_parsed = [nom_service.parse_place(p) for p in nominatim]
    merged: list[dict] = list(nominatim)  # keep raw OSM dicts so _parse_place works later

    for gp in google:
        if not any(_dist(gp, np) < 50 for np in nom_parsed):
            merged.append(gp)

    return merged


def _generate_reasons(restaurants: list[Restaurant], parsed: ParsedQuery) -> dict[str, str]:
    """
    Generates Traditional Chinese recommendation reasons using templates.
    # EXTENSION POINT: personalise based on user's saved favourites or past ratings.
    """
    food_labels = {
        "healthy restaurant":          "健康料理",
        "vegetarian restaurant":       "素食",
        "noodle restaurant":           "麵食",
        "fast food restaurant":        "速食",
        "restaurant":                  "餐廳",
        "japanese restaurant":         "日式料理",
        "taiwanese restaurant":        "台式料理",
        "breakfast cafe":              "早餐",
        "cafe":                        "咖啡廳",
        "korean restaurant":           "韓式料理",
        "western restaurant":          "西式料理",
        "hotpot restaurant":           "火鍋",
        "chinese restaurant":          "中式料理",
        "asian restaurant":            "亞洲料理",
        "dessert shop":                "甜點店",
        "bubble tea shop":             "手搖飲料店",
        "italian restaurant":          "義大利料理",
        "steak restaurant":            "牛排館",
        "rice restaurant":             "飯類料理",
    }
    # Use the raw keyword the user typed ("冰品", "火鍋") when available — more natural
    label = parsed.raw_keyword or food_labels.get(parsed.food, parsed.food)

    reasons: dict[str, str] = {}
    for r in restaurants:
        min_str = f"{r.walking_minutes:.0f}"
        reasons[r.id] = (
            f"提供{label}，距您步行約 {min_str} 分鐘可到達，"
            f"符合您「{parsed.time}分鐘以內」的需求。"
        )
    return reasons


def _spin_time_hint(hour: int) -> str:
    if 6 <= hour < 10:    return "早安！早餐時間推薦你來這個 🌅"
    if 10 <= hour < 14:   return "午餐時間到了，命運之輪幫你選好了！🌞"
    if 14 <= hour < 17:   return "下午茶時刻，讓命運決定吧 ☕"
    if 17 <= hour < 21:   return "晚餐時間！今晚就吃這個 🌆"
    return "深夜了還在吃？好吧，輪盤說了算 🌙"


app = create_app()
