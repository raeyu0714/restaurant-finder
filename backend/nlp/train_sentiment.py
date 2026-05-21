"""
Sentiment Model Training — TF-IDF + Logistic Regression
Input : data/reviews.json  (from collect_reviews.py)
Output: backend/nlp/models/sentiment_clf.pkl
        backend/nlp/models/sentiment_tfidf.pkl

Run: python -m backend.nlp.train_sentiment  (from project root)
"""
import json
import os
import jieba
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report

DATA_PATH  = os.path.join(os.path.dirname(__file__), "../../data/reviews.json")
MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models")


def tokenize(text: str) -> str:
    return " ".join(jieba.cut(text))


def load_and_label(path: str):
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    texts, labels = [], []
    skipped = 0
    for r in records:
        rating = r.get("rating", 0)
        text   = (r.get("text") or "").strip()
        if not text:
            continue
        if rating >= 4:
            labels.append(1)   # positive
            texts.append(text)
        elif rating <= 2:
            labels.append(0)   # negative
            texts.append(text)
        else:
            skipped += 1       # skip 3-star — too ambiguous

    print(f"Loaded  : {len(texts)} reviews  (skipped {skipped} neutral ★3)")
    print(f"Positive: {sum(labels)}  |  Negative: {len(labels) - sum(labels)}")
    return texts, labels


def train(texts, labels):
    print("\n=== Tokenising with jieba ===")
    tokenised = [tokenize(t) for t in texts]

    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=8000,
        sublinear_tf=True,
        min_df=2,
    )
    X = tfidf.fit_transform(tokenised)
    y = np.array(labels)

    print("\n=== Cross-validating ===")
    clf = LogisticRegression(C=2.0, max_iter=1000, random_state=42)
    cv  = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
    print(f"CV Accuracy: {scores.mean():.3f} ± {scores.std():.3f}")

    print("\n=== Training on full dataset ===")
    clf.fit(X, y)
    preds = clf.predict(X)
    print(classification_report(y, preds, target_names=["負評", "好評"]))

    return tfidf, clf


def save(tfidf, clf):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(tfidf, os.path.join(MODEL_DIR, "sentiment_tfidf.pkl"))
    joblib.dump(clf,   os.path.join(MODEL_DIR, "sentiment_clf.pkl"))
    print(f"\n[✓] Saved to {MODEL_DIR}/")
    print("  - sentiment_tfidf.pkl")
    print("  - sentiment_clf.pkl")


if __name__ == "__main__":
    texts, labels = load_and_label(DATA_PATH)
    if len(texts) < 20:
        print("Not enough data — run collect_reviews.py first.")
    else:
        tfidf, clf = train(texts, labels)
        save(tfidf, clf)
