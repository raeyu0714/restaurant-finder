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


class CreateGroupRequest(BaseModel):
    name: str


class InviteRequest(BaseModel):
    username: str


class SendMessageRequest(BaseModel):
    text: str


class VoteOption(BaseModel):
    id: str
    name: str
    address: str
    walking_minutes: float
    latitude: float
    longitude: float


class CreateVoteRequest(BaseModel):
    title: str
    options: list[VoteOption]


class CastVoteRequest(BaseModel):
    option_id: str


class RecognizeResponse(BaseModel):
    food_label: str    # Chinese food term, e.g. "珍珠奶茶"
    confidence: float  # 0.0–1.0
    query: str         # ready-to-use NLP query, e.g. "我想喝珍珠奶茶"


class SearchResponse(BaseModel):
    restaurants: list[Restaurant]
    parsed_query: ParsedQuery
    recommendation_reasons: dict[str, str]  # restaurant id → 繁體中文 reason
    favourite_ids: list[str] = []           # ids of restaurants that are favourited
    map_html: str                           # Folium _repr_html_() output (iframe)
    timestamp: str                          # ISO 8601
    signature: str                          # base64 RSA-PSS SHA-256
    signed_data: str                        # canonical JSON (excludes map_html + signature)
