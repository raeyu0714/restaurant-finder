"""
Review Collection Script — Outscraper Google Maps Reviews
Uses Account 1 API key (data collection quota).

Run:  python -m backend.scripts.collect_reviews --api-key YOUR_KEY
Output: data/reviews.json  (~450 reviews from 15 Hsinchu restaurants)
"""
import json
import os
import argparse
import time

# 15 restaurants in Hsinchu covering all our food categories
# Mix of chains (reliable review volume) + local favourites
RESTAURANTS = [
    # Ramen / Japanese
    "爭鮮迴轉壽司 新竹巨城店, Hsinchu, Taiwan",
    "一蘭拉麵 新竹, Hsinchu, Taiwan",
    # Hotpot
    "海底撈火鍋 新竹, Hsinchu, Taiwan",
    "呷七碗 新竹, Hsinchu, Taiwan",
    # Fast food / Burgers
    "麥當勞 新竹東區, Hsinchu, Taiwan",
    "摩斯漢堡 新竹, Hsinchu, Taiwan",
    # Steak / Western
    "王品牛排 新竹, Hsinchu, Taiwan",
    "西堤牛排 新竹, Hsinchu, Taiwan",
    # Taiwanese / Bento
    "鴨肉許 新竹城隍廟, Hsinchu, Taiwan",
    "排骨大王 新竹, Hsinchu, Taiwan",
    # Cafe / Brunch
    "星巴克 新竹Big City, Hsinchu, Taiwan",
    "路易莎咖啡 新竹, Hsinchu, Taiwan",
    # Bubble tea
    "50嵐 新竹, Hsinchu, Taiwan",
    "珍煮丹 新竹, Hsinchu, Taiwan",
    # Dessert
    "85度C 新竹, Hsinchu, Taiwan",
]

REVIEWS_PER_PLACE = 30   # 15 × 30 = 450 reviews, within 500 free limit
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../../data/reviews.json")


def collect(api_key: str):
    try:
        from outscraper import OutscraperClient
    except ImportError:
        print("Install outscraper first:  pip install outscraper")
        return

    client = OutscraperClient(api_key=api_key)
    all_reviews = []

    for i, restaurant in enumerate(RESTAURANTS, 1):
        print(f"[{i}/{len(RESTAURANTS)}] Fetching: {restaurant}")
        try:
            results = client.google_maps_reviews(
                restaurant,
                reviews_limit=REVIEWS_PER_PLACE,
                language="zh-TW",
                sort="most_relevant",
            )

            count = 0
            for place in results:
                for review in place.get("reviews_data", []):
                    text   = (review.get("review_text") or "").strip()
                    rating = review.get("review_rating")
                    if not text or rating is None:
                        continue
                    all_reviews.append({
                        "restaurant": place.get("name", restaurant),
                        "text":       text,
                        "rating":     int(rating),
                    })
                    count += 1

            print(f"  → {count} reviews collected")
            time.sleep(1)   # be polite to the API

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=2)

    pos = sum(1 for r in all_reviews if r["rating"] >= 4)
    neg = sum(1 for r in all_reviews if r["rating"] <= 2)
    neu = sum(1 for r in all_reviews if r["rating"] == 3)
    print(f"\n=== Done ===")
    print(f"Total reviews : {len(all_reviews)}")
    print(f"Positive (4-5): {pos}")
    print(f"Negative (1-2): {neg}")
    print(f"Neutral  (3)  : {neu}  (will be skipped in training)")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="Outscraper API key (Account 1)")
    args = parser.parse_args()
    collect(args.api_key)
