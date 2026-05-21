"""
NLP Inference — MiniLM embeddings + Logistic Regression intent classifier.
Handles typos, indirect phrases, and contextual statements by encoding with
a multilingual sentence transformer before classifying.
"""
import os
import re
import joblib
import numpy as np
import jieba
import jieba.posseg as _pseg
from functools import lru_cache

# Teach jieba about foreign-loanword food nouns it may mis-segment
for _w in [
    "披薩", "漢堡", "沙拉", "帕尼尼", "布里托", "塔可", "卡布奇諾", "拿鐵", "法棍",
    "麥當勞", "肯德基", "必勝客", "星巴克", "漢堡王", "摩斯漢堡", "摩斯",
    "鼎泰豐", "爭鮮", "吉野家", "丼飯", "便當",
]:
    jieba.add_word(_w, freq=10000, tag="n")
# Reinforce common words that jieba may mis-segment in food context
for _w in ["距離", "步行", "走路", "分鐘", "以內"]:
    jieba.add_word(_w, freq=10000)

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models")
MODEL_NAME = os.path.join(os.path.dirname(__file__), "local_model")

DEFAULT_TIME         = 15
CONFIDENCE_THRESHOLD = 0.35   # below this → find_general

# ── Out-of-domain / special-intent detector ──────────────────────────────────
# Recipe / cooking: user wants instructions, not a restaurant.
_OOD_PATTERNS = re.compile(r'(怎麼做|怎麼煮|食譜|做法|在家煮|自己做|自己煮|怎樣煮|怎麼自己|教我煮|教我做)')

# Navigation / emergency: user needs a clinic/hospital, not food.
_NAVIGATION_PATTERNS = re.compile(r'(診所|醫院|救護|急診|警察局|藥局|藥房|消防)')

# Complaint / emotional venting: detect rage-quit / frustration phrases.
_COMPLAINT_PATTERNS = re.compile(r'(到底有什麼用|我要刪掉|這什麼爛|爛App|爛地圖|有什麼用|刪掉了|退費|客服)')

# Exclusion framing: "除了X之外" means the user is EXCLUDING X, not searching for it.
_EXCLUSION_FRAME = re.compile(r'除了.{0,30}(之外|以外)')

# ── Time extraction ───────────────────────────────────────────────────────────
_CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

def _cn_to_int(s: str) -> int | None:
    """Convert a simple Chinese numeral string (up to 99) to int."""
    s = s.strip()
    if s in _CN_NUM_MAP:
        return _CN_NUM_MAP[s]
    if len(s) == 2:
        if s[0] == "十":
            return 10 + _CN_NUM_MAP.get(s[1], 0)   # 十五 → 15
        if s[1] == "十":
            return _CN_NUM_MAP.get(s[0], 0) * 10   # 二十 → 20
    if len(s) == 3 and s[1] == "十":               # 二十五 → 25
        return _CN_NUM_MAP.get(s[0], 0) * 10 + _CN_NUM_MAP.get(s[2], 0)
    return None


@lru_cache(maxsize=1)
def _load_models():
    encoder       = SentenceTransformer(MODEL_NAME)
    clf           = joblib.load(os.path.join(MODEL_DIR, "intent_clf.pkl"))
    label_encoder = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))
    slot_patterns = joblib.load(os.path.join(MODEL_DIR, "slot_patterns.pkl"))
    food_type_map = joblib.load(os.path.join(MODEL_DIR, "food_type_map.pkl"))
    return encoder, clf, label_encoder, slot_patterns, food_type_map


# Non-food context words — skip them silently before food collection starts,
# stop collection if they appear mid-sequence.
_SKIP_WORDS = {
    "東西", "食物", "一下", "什麼", "點東", "吃的", "好吃", "料理", "好的", "一些",
    "附近", "一家", "這裡", "那裡", "哪裡", "地方", "這邊", "那邊",
    "走路", "步行", "超近",                    # movement / proximity — not food
    "早餐", "午餐", "晚餐", "晚飯", "早午餐", "宵夜", "消夜",  # meal types — handled separately
}

# Segments to skip over (measure words, particles, time units)
_SKIP_SEGS = {
    "個", "份", "碗", "盤", "杯", "瓶", "口", "頓", "點", "些",
    "的", "了", "嗎", "吧", "啊", "呢", "喔", "唷", "耶", "囉", "哦", "呀",
    "鐘", "分鐘", "小時", "半",                # time units
    "距離", "附近", "旁邊", "周圍", "範圍", "以內", "以外",  # spatial context
}

# POS flag prefixes that STOP food collection (verbs, adjectives, pronouns, locality, etc.)
_STOP_FLAG_PREFIXES = ('v', 'a', 'r', 'c', 'd', 'p', 'u', 'f')

# POS flag prefixes to skip over silently (numbers, quantifiers like "一碗", "三份")
_SKIP_FLAG_PREFIXES = ('m', 'q')

# Single/ambiguous characters → expand to a more searchable term
_KEYWORD_EXPAND = {
    "冰":   "冰淇淋",
    "甜":   "甜點",
    "鍋":   "火鍋",
    "麵":   "麵食",
    "飯":   "飯食",
    "肉":   "燒肉",
    "魚":   "海鮮",
    "湯":   "湯品",
    "點心": "甜點",
    "飲料": "手搖飲料",
    "喝的": "手搖飲料",
    "咖啡": "咖啡廳",
    "茶":   "手搖茶",
    "奶茶": "珍珠奶茶",
}

_CJK = re.compile(r'^[一-鿿]{1,8}$')

# Common spelling variants → normalise before searching
_SPELLING_NORMALIZE = {
    "咖喱": "咖哩",
    "咖哩": "咖哩",
    "漢堡排": "漢堡",
    "薯條": "速食",
}


def _extract_food_keyword(text: str) -> str | None:
    """
    Extracts the food word using jieba POS-aware word segmentation on the full text.

    Running the segmenter on the full sentence gives correct word boundaries:
      '我要吃壽司慶祝' → 壽司(n) 慶祝(v)  →  stops at the verb  →  '壽司'
      '吃個雞腿飯好了' → 雞(n) 腿(n) 飯(n) 好(a)  →  stops at adjective  →  '雞腿飯'

    No food dictionary needed — works for any word jieba can segment.
    """
    actions = ["想吃", "要吃", "想喝", "要喝", "去吃", "吃個", "喝個", "吃點", "喝點",
               "享用", "來個", "來碗", "來杯", "來份", "來盤", "想來", "有賣", "想要",
               "請吃", "請喝", "請個", "請來",
               "找", "吃", "喝", "來", "請"]

    segs = list(_pseg.cut(text))   # full-text segmentation for best accuracy

    for action in sorted(actions, key=len, reverse=True):
        action_idx = text.find(action)
        if action_idx == -1:
            continue
        after_char = action_idx + len(action)

        # Find the first segment that begins at or after after_char
        char_pos, after_seg = 0, len(segs)
        for i, (seg, _) in enumerate(segs):
            if char_pos >= after_char:
                after_seg = i
                break
            char_pos += len(seg)

        parts: list[str] = []
        for seg, flag in segs[after_seg:after_seg + 8]:
            # Skip measure words and particles whether or not we've started
            if seg in _SKIP_SEGS:
                if parts:
                    break        # already collecting → end of food name
                continue         # not yet collecting → skip over

            # Skip non-food context words before we start collecting
            if seg in _SKIP_WORDS and not parts:
                continue

            # Non-CJK character (number, latin, etc.) ends the scan
            if not _CJK.match(seg):
                break

            # Numbers and quantifiers (一碗, 三份) — skip silently
            if flag.startswith(_SKIP_FLAG_PREFIXES):
                continue

            # Verb / adjective / pronoun / etc. normally ends the food name.
            # Exception: short verb tokens (1-3 chars) at the very start can be
            # food-verb compounds (炒飯, 燒肉, 拉麵, 烤雞).  Jieba often tags the
            # whole compound as 'v'.  Include provisionally; if nothing follows
            # it gets returned as-is.
            if flag.startswith(_STOP_FLAG_PREFIXES):
                if len(seg) <= 3 and flag.startswith('v') and not parts:
                    parts.append(seg)
                    continue
                break

            parts.append(seg)
            if len("".join(parts)) >= 5:  # cap at 5 chars
                break

        if len(parts) >= 2 or (len(parts) == 1 and parts[0] not in _SKIP_SEGS):
            word = "".join(parts)
            word = _SPELLING_NORMALIZE.get(word, word)
            return _KEYWORD_EXPAND.get(word, word)

    return None


def _extract_time(text: str, slot_patterns: dict) -> int:
    # "半小時" → 30 min
    if re.search(r'半\s*個?\s*小時', text):
        return 30

    # digit + 小時 → N * 60 min
    m = re.search(r'(\d+)\s*小時', text)
    if m:
        return int(m.group(1)) * 60

    # Chinese number + 小時
    m = re.search(r'([一二兩三四五六七八九十]+)\s*小時', text)
    if m:
        n = _cn_to_int(m.group(1))
        if n:
            return n * 60

    # digit + min / 分鐘 — unambiguous time unit
    m = re.search(r'(\d+)\s*(?:min|mins|分鐘)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # digit + bare 分 — colloquial shorthand (e.g. "走十分就到")
    # Reject values ≥ 60: "100分", "90分" are almost always scores, not durations
    m = re.search(r'(\d+)\s*分(?!鐘)', text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 59:
            return n

    # Colloquial range like "三五分鐘", "四五分鐘" → take the upper (larger) digit
    m = re.search(r'([一二三四五六七八九])([二三四五六七八九])\s*分', text)
    if m:
        return max(_CN_NUM_MAP.get(m.group(1), 0), _CN_NUM_MAP.get(m.group(2), 0))

    # Standard Chinese number + 分鐘
    m = re.search(r'([一二兩三四五六七八九十]+)\s*分鐘', text)
    if m:
        n = _cn_to_int(m.group(1))
        if n:
            return n

    return DEFAULT_TIME


def _extract_meal(text: str, slot_patterns: dict) -> str | None:
    if slot_patterns["meal_breakfast"].search(text): return "breakfast"
    if slot_patterns["meal_lunch"].search(text):     return "lunch"
    if slot_patterns["meal_dinner"].search(text):    return "dinner"
    if slot_patterns["meal_afternoon"].search(text): return "afternoon"
    return None


def _build_keywords(intent: str, meal: str | None) -> list[str]:
    keywords = []
    if meal == "breakfast":   keywords.append("breakfast")
    elif meal == "lunch":     keywords.append("lunch")
    elif meal == "dinner":    keywords.append("dinner")
    elif meal == "afternoon": keywords.append("cafe")
    modifiers = {
        "find_japanese":        ["japanese", "sushi", "ramen"],
        "find_korean":          ["korean", "bbq"],
        "find_western":         ["western", "pizza"],
        "find_hotpot":          ["hotpot"],
        "find_chinese":         ["chinese", "dim sum"],
        "find_southeast_asian": ["vietnamese", "thai"],
        "find_cafe":            ["cafe", "coffee"],
        "find_healthy":         ["healthy", "salad"],
        "find_vegetarian":      ["vegetarian", "vegan"],
        "find_dessert":         ["dessert", "cake", "sweets"],
        "find_drinks":          ["bubble tea", "drinks", "milk tea"],
        "find_fast_food":       ["fast food", "麥當勞", "肯德基"],
        "find_pasta":           ["pasta", "italian", "義大利麵"],
        "find_steak":           ["steak", "牛排"],
        "find_rice":            ["rice", "炒飯", "飯"],
    }
    keywords.extend(modifiers.get(intent, [])[:2])
    return list(dict.fromkeys(keywords))


def predict(text: str) -> dict:
    # Fast special-intent checks before the ML pipeline runs
    if _OOD_PATTERNS.search(text):
        return {"intent": "out_of_domain",  "food": "restaurant", "time": DEFAULT_TIME,
                "meal": None, "keywords": [], "raw_keyword": None}
    if _NAVIGATION_PATTERNS.search(text):
        return {"intent": "navigation",     "food": "restaurant", "time": DEFAULT_TIME,
                "meal": None, "keywords": [], "raw_keyword": None}
    if _COMPLAINT_PATTERNS.search(text):
        return {"intent": "complaint",      "food": "restaurant", "time": DEFAULT_TIME,
                "meal": None, "keywords": [], "raw_keyword": None}

    encoder, clf, label_encoder, slot_patterns, food_type_map = _load_models()

    emb   = encoder.encode([text], convert_to_numpy=True, normalize_embeddings=True)
    proba = clf.predict_proba(emb)[0]
    top_idx  = proba.argmax()
    top_prob = proba[top_idx]

    if top_prob >= CONFIDENCE_THRESHOLD:
        intent = label_encoder.inverse_transform([top_idx])[0]
    else:
        intent = "find_general"

    # "除了X之外" means X is being excluded — re-classify on the remaining text
    # so the WANTED cuisine (after 之外) is detected, not the excluded one.
    excl_text = text
    excl_match = _EXCLUSION_FRAME.search(text)
    if excl_match:
        excl_text = text[:excl_match.start()] + text[excl_match.end():]
        # Re-classify on the stripped text
        excl_emb   = encoder.encode([excl_text], convert_to_numpy=True, normalize_embeddings=True)
        excl_proba = clf.predict_proba(excl_emb)[0]
        excl_idx   = excl_proba.argmax()
        if excl_proba[excl_idx] >= CONFIDENCE_THRESHOLD:
            intent = label_encoder.inverse_transform([excl_idx])[0]
        else:
            intent = "find_general"

    max_time    = _extract_time(text, slot_patterns)
    meal        = _extract_meal(text, slot_patterns)
    raw_keyword = _extract_food_keyword(text)

    from ..services.nominatim import CUISINE_TEXT_QUERIES
    inv_map = {v: k for k, v in food_type_map.items()}

    if intent == "find_general" and raw_keyword:
        # Fallback 1: re-classify the food keyword alone
        kw_emb   = encoder.encode([raw_keyword], convert_to_numpy=True, normalize_embeddings=True)
        kw_proba = clf.predict_proba(kw_emb)[0]
        kw_idx   = kw_proba.argmax()
        if kw_proba[kw_idx] >= CONFIDENCE_THRESHOLD:
            intent = label_encoder.inverse_transform([kw_idx])[0]

    if intent == "find_general" and raw_keyword:
        # Fallback 2: substring-match raw_keyword against CUISINE_TEXT_QUERIES
        for food_type, queries in CUISINE_TEXT_QUERIES.items():
            if any(q in raw_keyword or raw_keyword in q for q in queries):
                inferred = inv_map.get(food_type)
                if inferred:
                    intent = inferred
                    break

    # Venue-type scan: explicit venue mention in text overrides ambiguous intents.
    # Use excl_text (exclusion phrase removed) so we don't match the excluded cuisine.
    if intent in ("find_general", "find_drinks", "find_dessert"):
        for food_type, queries in CUISINE_TEXT_QUERIES.items():
            if any(q in excl_text for q in queries):
                inferred = inv_map.get(food_type)
                if inferred and inferred not in ("find_general",):
                    intent = inferred
                    break

    # Keyword-cuisine mismatch: raw_keyword directly names a different cuisine
    # (e.g. classifier says find_rice but user typed "咖哩").
    # Only override when raw_keyword matches a CUISINE_TEXT_QUERIES term exactly.
    if raw_keyword and intent not in ("find_general",):
        for food_type, queries in CUISINE_TEXT_QUERIES.items():
            if any(q in raw_keyword or raw_keyword in q for q in queries):
                inferred = inv_map.get(food_type)
                if inferred and inferred != intent and inferred != "find_general":
                    intent = inferred
                    break

    food     = food_type_map.get(intent, "restaurant")
    keywords = _build_keywords(intent, meal)

    return {
        "intent":      intent,
        "food":        food,
        "time":        max_time,
        "meal":        meal,
        "keywords":    keywords,
        "raw_keyword": raw_keyword,
    }


def models_exist() -> bool:
    if not _ST_AVAILABLE:
        return False
    required = ["intent_clf.pkl", "label_encoder.pkl", "slot_patterns.pkl", "food_type_map.pkl"]
    return all(os.path.exists(os.path.join(MODEL_DIR, f)) for f in required)
