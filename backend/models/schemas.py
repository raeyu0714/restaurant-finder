from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    latitude: float
    longitude: float
    use_google: bool = False


class ParsedQuery(BaseModel):
    intent: str
    food: str
    time: int
    meal: Optional[str] = None
    keywords: list[str] = []
    raw_keyword: Optional[str] = None   # food word extracted directly from text


class Restaurant(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    address: str
    walking_minutes: float
    osm_type: str
    osm_id: int
    rating: Optional[float] = None
    review_count: Optional[int] = None
    reviews: list[str] = []


class RegisterRequest(BaseModel):
    username: str
    password: str


class FavouriteRequest(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    address: str


class SearchResponse(BaseModel):
    restaurants: list[Restaurant]
    parsed_query: ParsedQuery
    recommendation_reasons: dict[str, str]  # restaurant id → 繁體中文 reason
    favourite_ids: list[str] = []           # ids of restaurants that are favourited
    map_html: str                           # Folium _repr_html_() output (iframe)
    timestamp: str                          # ISO 8601
    signature: str                          # base64 RSA-PSS SHA-256
    signed_data: str                        # canonical JSON (excludes map_html + signature)
