"""
Two-stage food recognition pipeline:
  Stage 1: YOLOv8n (COCO) — soft food-presence gate
  Stage 2: fine-tuned nateraw/food ViT-B (110 classes) — classification

Both models are loaded once via lru_cache (warm on first request, cached after).
Inference RAM: ~400 MB on HuggingFace Spaces.
"""
import io
import json
import os
from functools import lru_cache

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

VIT_MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models", "food_vit")
CLASS_IDX_PATH = os.path.join(VIT_MODEL_DIR, "class_to_idx.json")

# COCO classes that strongly suggest edible food is present
_YOLO_FOOD_CLASSES = {
    "apple", "banana", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "sandwich",
    "bowl", "cup",           # proxy — often contain food
}

# Mapping: ImageFolder class directory name → Chinese search term
# Food-101 uses underscored English names; Taiwanese classes added separately.
FOOD_LABEL_MAP: dict[str, str] = {
    # ── 9 Taiwanese classes ─────────────────────────────────────────────────
    "bubble_tea":            "珍珠奶茶",
    "beef_noodle_soup":      "牛肉麵",
    "braised_pork_rice":     "滷肉飯",
    "soup_dumplings":        "小籠包",
    "fried_chicken_steak":   "雞排",
    "stinky_tofu":           "臭豆腐",
    "gua_bao":               "刈包",
    "scallion_pancake":      "蔥油餅",
    "oyster_omelette":       "蚵仔煎",
    # ── Food-101 (101 classes) ───────────────────────────────────────────────
    "apple_pie":             "甜點",
    "baby_back_ribs":        "燒烤",
    "baklava":               "甜點",
    "beef_carpaccio":        "西式料理",
    "beef_tartare":          "法式料理",
    "beet_salad":            "沙拉",
    "beignets":              "甜點",
    "bibimbap":              "韓式拌飯",
    "bread_pudding":         "甜點",
    "breakfast_burrito":     "早午餐",
    "bruschetta":            "義式料理",
    "caesar_salad":          "沙拉",
    "cannoli":               "甜點",
    "caprese_salad":         "義式料理",
    "carrot_cake":           "甜點",
    "ceviche":               "海鮮",
    "cheesecake":            "甜點",
    "cheese_plate":          "西式料理",
    "chicken_curry":         "咖哩",
    "chicken_quesadilla":    "墨西哥料理",
    "chicken_wings":         "炸雞翅",
    "chocolate_cake":        "甜點",
    "chocolate_mousse":      "甜點",
    "churros":               "甜點",
    "clam_chowder":          "濃湯",
    "club_sandwich":         "三明治",
    "crab_cakes":            "海鮮",
    "creme_brulee":          "甜點",
    "croque_madame":         "法式料理",
    "cup_cakes":             "甜點",
    "deviled_eggs":          "早午餐",
    "donuts":                "甜甜圈",
    "dumplings":             "水餃",
    "edamame":               "居酒屋",
    "eggs_benedict":         "早午餐",
    "escargots":             "法式料理",
    "falafel":               "中東料理",
    "filet_mignon":          "牛排",
    "fish_and_chips":        "英式料理",
    "foie_gras":             "法式料理",
    "french_fries":          "薯條",
    "french_onion_soup":     "法式料理",
    "french_toast":          "早午餐",
    "fried_calamari":        "海鮮",
    "fried_rice":            "炒飯",
    "frozen_yogurt":         "冰淇淋",
    "garlic_bread":          "麵包",
    "gnocchi":               "義大利料理",
    "greek_salad":           "沙拉",
    "grilled_cheese_sandwich": "三明治",
    "grilled_salmon":        "海鮮",
    "guacamole":             "墨西哥料理",
    "gyoza":                 "煎餃",
    "hamburger":             "漢堡",
    "hot_and_sour_soup":     "酸辣湯",
    "hot_dog":               "熱狗",
    "huevos_rancheros":      "早午餐",
    "hummus":                "中東料理",
    "ice_cream":             "冰淇淋",
    "lasagna":               "義大利料理",
    "lobster_bisque":        "海鮮",
    "lobster_roll_sandwich": "海鮮",
    "macaroni_and_cheese":   "美式料理",
    "macarons":              "甜點",
    "miso_soup":             "日本料理",
    "mussels":               "海鮮",
    "nachos":                "墨西哥料理",
    "omelette":              "早午餐",
    "onion_rings":           "美式料理",
    "oysters":               "海鮮",
    "pad_thai":              "泰式料理",
    "paella":                "西班牙料理",
    "pancakes":              "鬆餅",
    "panna_cotta":           "甜點",
    "peking_duck":           "北京烤鴨",
    "pho":                   "越南河粉",
    "pizza":                 "披薩",
    "pork_chop":             "豬排",
    "poutine":               "薯條",
    "prime_rib":             "牛排",
    "pulled_pork_sandwich":  "美式料理",
    "ramen":                 "拉麵",
    "ravioli":               "義大利料理",
    "red_velvet_cake":       "甜點",
    "risotto":               "義大利料理",
    "samosa":                "印度料理",
    "sashimi":               "生魚片",
    "scallops":              "海鮮",
    "seaweed_salad":         "日本料理",
    "shrimp_and_grits":      "海鮮",
    "spaghetti_bolognese":   "義大利麵",
    "spaghetti_carbonara":   "義大利麵",
    "spring_rolls":          "春捲",
    "steak":                 "牛排",
    "strawberry_shortcake":  "甜點",
    "sushi":                 "壽司",
    "tacos":                 "墨西哥料理",
    "takoyaki":              "章魚燒",
    "tiramisu":              "甜點",
    "tuna_tartare":          "海鮮",
    "waffles":               "鬆餅",
}

# Labels that suggest drinking rather than eating
_DRINK_KEYWORDS = ("茶", "奶茶", "飲料", "咖啡", "飲", "汁")


@lru_cache(maxsize=1)
def _load_yolo():
    try:
        from ultralytics import YOLO
        return YOLO("yolov8n.pt")   # auto-downloads ~6 MB COCO weights
    except Exception:
        return None


@lru_cache(maxsize=1)
def _load_vit():
    extractor   = AutoImageProcessor.from_pretrained(VIT_MODEL_DIR)
    model       = AutoModelForImageClassification.from_pretrained(VIT_MODEL_DIR)
    model.eval()
    class_to_idx = json.loads(open(CLASS_IDX_PATH, encoding="utf-8").read())
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    return extractor, model, idx_to_class


def _vit_available() -> bool:
    return os.path.isfile(CLASS_IDX_PATH)


def recognize(image_bytes: bytes) -> dict:
    """
    Returns {"food_label": str, "confidence": float, "query": str}
    Raises ValueError with a user-friendly Traditional Chinese message on failure.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Stage 1: YOLOv8n food gate (non-blocking — only warns, doesn't hard-reject)
    yolo = _load_yolo()
    food_hints: set[str] = set()
    if yolo is not None:
        try:
            results = yolo(img, verbose=False)
            if results and results[0].boxes is not None:
                for cls_id in results[0].boxes.cls:
                    food_hints.add(results[0].names[int(cls_id)])
        except Exception:
            pass

    # Stage 2: ViT-B 110-class classification
    if not _vit_available():
        raise ValueError(
            "食物辨識模型尚未就緒。請先完成訓練並將模型放入 backend/cv/models/food_vit/"
        )

    extractor, model, idx_to_class = _load_vit()
    inputs = extractor(images=img, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    probs      = torch.softmax(logits, dim=1)[0]
    top1_idx   = int(probs.argmax())
    top1_conf  = float(probs[top1_idx])

    if top1_conf < 0.20:
        raise ValueError("圖片中未偵測到明確食物，請嘗試更清晰的食物照片")

    class_name = idx_to_class[top1_idx]
    zh = FOOD_LABEL_MAP.get(class_name)

    # Top-5 fallback if top-1 label not mapped
    if not zh:
        for idx in probs.topk(5).indices.tolist():
            candidate = idx_to_class.get(idx, "")
            zh = FOOD_LABEL_MAP.get(candidate)
            if zh:
                top1_conf = float(probs[idx])
                break

    if not zh:
        raise ValueError(f"無法識別食物類型（{class_name}），請嘗試其他照片")

    verb = "喝" if any(k in zh for k in _DRINK_KEYWORDS) else "吃"
    return {
        "food_label": zh,
        "confidence": round(top1_conf, 4),
        "query": f"我想{verb}{zh}",
    }
