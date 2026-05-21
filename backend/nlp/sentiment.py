"""
Sentiment inference — loaded once, called per restaurant at search time.
Uses Account 2 Outscraper API key (demo quota).
"""
import os
import re
import jieba
import joblib
import httpx
from functools import lru_cache

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

POSITIVE_KEYWORDS = ["好吃", "美味", "推薦", "新鮮", "服務好", "划算", "CP值", "好喝", "香", "讚"]
NEGATIVE_KEYWORDS = ["難吃", "太鹹", "太油", "服務差", "慢", "貴", "失望", "冷", "硬", "差"]


@lru_cache(maxsize=1)
def _load_models():
    tfidf = joblib.load(os.path.join(MODEL_DIR, "sentiment_tfidf.pkl"))
    clf   = joblib.load(os.path.join(MODEL_DIR, "sentiment_clf.pkl"))
    return tfidf, clf


def models_exist() -> bool:
    return all(
        os.path.exists(os.path.join(MODEL_DIR, f))
        for f in ["sentiment_tfidf.pkl", "sentiment_clf.pkl"]
    )


def _tokenize(text: str) -> str:
    return " ".join(jieba.cut(text))


def predict_sentiment(reviews: list[str]) -> dict:
    """
    Takes a list of review strings, returns:
      { "score": 0.87, "label": "好評", "count": 18,
        "positive_keywords": ["好吃","推薦"], "negative_keywords": [] }
    """
    if not reviews or not models_exist():
        return {"score": None, "label": "無評論", "count": 0,
                "positive_keywords": [], "negative_keywords": []}

    tfidf, clf = _load_models()

    tokenised = [_tokenize(r) for r in reviews]
    X         = tfidf.transform(tokenised)
    probas    = clf.predict_proba(X)[:, 1]   # probability of positive
    score     = float(probas.mean())

    combined = " ".join(reviews)
    pos_kw = [w for w in POSITIVE_KEYWORDS if w in combined][:3]
    neg_kw = [w for w in NEGATIVE_KEYWORDS if w in combined][:2]

    if score >= 0.70:
        label = "好評"
    elif score >= 0.45:
        label = "普通"
    else:
        label = "負評"

    return {
        "score":             round(score, 3),
        "label":             label,
        "count":             len(reviews),
        "positive_keywords": pos_kw,
        "negative_keywords": neg_kw,
    }


async def fetch_and_predict(
    place_name: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> dict:
    """
    Calls Outscraper REST API to get reviews, then runs sentiment prediction.
    Falls back to {"score": None} silently on any error.
    """
    if not api_key or not models_exist():
        return {"score": None, "label": "無評論", "count": 0,
                "positive_keywords": [], "negative_keywords": []}
    try:
        resp = await client.get(
            "https://api.app.outscraper.com/maps/reviews-v3",
            params={
                "query":        place_name,
                "reviewsLimit": 20,
                "language":     "zh-TW",
                "sort":         "most_relevant",
            },
            headers={"X-API-KEY": api_key},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        reviews = []
        for place in data.get("data", []):
            for r in place.get("reviews_data", []):
                text = (r.get("review_text") or "").strip()
                if text:
                    reviews.append(text)

        return predict_sentiment(reviews)

    except Exception:
        return {"score": None, "label": "無評論", "count": 0,
                "positive_keywords": [], "negative_keywords": []}
