"""
NLP Training Script — Semantic Intent Classification
Strategy: MiniLM embeddings + Logistic Regression classifier
  - MiniLM handles semantic understanding (typos, indirect phrases)
  - LogReg learns food-type decision boundaries on top of embeddings

Run: python -m backend.nlp.train  (from project root)
"""
import json
import re
import os
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder

DATA_PATH   = os.path.join(os.path.dirname(__file__), "../../data/train_data.json")
MODEL_DIR   = os.path.join(os.path.dirname(__file__), "models")
_LOCAL_MODEL = os.path.join(os.path.dirname(__file__), "local_model")
MODEL_NAME  = _LOCAL_MODEL if os.path.isdir(_LOCAL_MODEL) else "paraphrase-multilingual-MiniLM-L12-v2"


def load_data(path: str):
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    return (
        [r["text"]   for r in records],
        [r["intent"] for r in records],
        [r["slots"]  for r in records],
    )


def augment_data(texts, intents, slots):
    aug_texts, aug_intents, aug_slots = list(texts), list(intents), list(slots)
    variants = {
        "分鐘內": ["分鐘以內", "分鐘之內"],
        "走路":   ["步行", "走"],
        "附近":   ["周邊", "旁邊", "鄰近"],
        "推薦":   ["介紹", "建議"],
    }
    for text, intent, slot in zip(texts, intents, slots):
        for original, replacements in variants.items():
            if original in text:
                new_text = text.replace(original, replacements[0], 1)
                if new_text not in aug_texts:
                    aug_texts.append(new_text)
                    aug_intents.append(intent)
                    aug_slots.append(slot)
                break
    return aug_texts, aug_intents, aug_slots


def encode(texts: list[str], model: SentenceTransformer) -> np.ndarray:
    return model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )


def train_classifier(embeddings: np.ndarray, intents: list[str]):
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(intents)

    clf = LogisticRegression(C=5.0, max_iter=1000, random_state=42)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, embeddings, y, cv=cv, scoring="accuracy")
    print(f"CV Accuracy: {scores.mean():.3f} ± {scores.std():.3f}")

    clf.fit(embeddings, y)
    train_acc = (clf.predict(embeddings) == y).mean()
    print(f"Train Accuracy: {train_acc:.3f}")

    return clf, label_encoder


def extract_slot_patterns():
    return {
        "max_time":       re.compile(r"(\d+)\s*分鐘"),
        "meal_lunch":     re.compile(r"午餐|中餐|中午"),
        "meal_dinner":    re.compile(r"晚餐|晚飯|晚上"),
        "meal_breakfast": re.compile(r"早餐|早飯|早上|早午餐|brunch"),
        "meal_afternoon": re.compile(r"下午茶|點心"),
    }


def build_food_type_map():
    return {
        "find_healthy":         "healthy restaurant",
        "find_vegetarian":      "vegetarian restaurant",
        "find_noodles":         "noodle restaurant",
        "find_fast_food":       "fast food restaurant",
        "find_general":         "restaurant",
        "find_japanese":        "japanese restaurant",
        "find_taiwanese":       "taiwanese restaurant",
        "find_breakfast":       "breakfast cafe",
        "find_cafe":            "cafe",
        "find_korean":          "korean restaurant",
        "find_western":         "western restaurant",
        "find_hotpot":          "hotpot restaurant",
        "find_chinese":         "chinese restaurant",
        "find_southeast_asian": "asian restaurant",
        "find_dessert":         "dessert shop",
        "find_drinks":          "bubble tea shop",
        "find_pasta":           "italian restaurant",
        "find_steak":           "steak restaurant",
        "find_rice":            "rice restaurant",
    }


def save_artifacts(embeddings, clf, label_encoder, slot_patterns, food_type_map):
    os.makedirs(MODEL_DIR, exist_ok=True)
    np.save(os.path.join(MODEL_DIR, "train_embeddings.npy"), embeddings)
    joblib.dump(clf,           os.path.join(MODEL_DIR, "intent_clf.pkl"))
    joblib.dump(label_encoder, os.path.join(MODEL_DIR, "label_encoder.pkl"))
    joblib.dump(slot_patterns, os.path.join(MODEL_DIR, "slot_patterns.pkl"))
    joblib.dump(food_type_map, os.path.join(MODEL_DIR, "food_type_map.pkl"))
    print(f"\n[✓] Models saved to {MODEL_DIR}/")
    for f in ["train_embeddings.npy", "intent_clf.pkl", "label_encoder.pkl",
              "slot_patterns.pkl", "food_type_map.pkl"]:
        print(f"  - {f}")


if __name__ == "__main__":
    print("=== Loading data ===")
    texts, intents, slots = load_data(DATA_PATH)
    print(f"{len(texts)} examples, {len(set(intents))} intents")

    print("\n=== Augmenting ===")
    texts, intents, slots = augment_data(texts, intents, slots)
    print(f"{len(texts)} examples after augmentation")

    print("\n=== Loading MiniLM from local_model/ ===")
    model = SentenceTransformer(MODEL_NAME)

    print("\n=== Encoding ===")
    embeddings = encode(texts, model)
    print(f"Shape: {embeddings.shape}")

    print("\n=== Training Logistic Regression classifier ===")
    clf, label_encoder = train_classifier(embeddings, intents)

    print("\n=== Saving ===")
    slot_patterns = extract_slot_patterns()
    food_type_map = build_food_type_map()
    save_artifacts(embeddings, clf, label_encoder, slot_patterns, food_type_map)
