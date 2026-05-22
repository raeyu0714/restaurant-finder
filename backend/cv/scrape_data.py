"""
Run once offline to scrape ~250 images per Taiwanese food class from Google Images.
Usage (from project root):
    pip install icrawler
    python backend/cv/scrape_data.py
"""
from icrawler.builtin import BingImageCrawler
import os

TAIWANESE_CLASSES = {
    "bubble_tea":          "珍珠奶茶 bubble tea Taiwan",
    "beef_noodle_soup":    "牛肉麵 beef noodle soup Taiwan",
    "braised_pork_rice":   "滷肉飯 braised pork rice Taiwan",
    "soup_dumplings":      "小籠包 soup dumplings xiao long bao",
    "fried_chicken_steak": "雞排 fried chicken steak Taiwan",
    "stinky_tofu":         "臭豆腐 stinky tofu Taiwan",
    "gua_bao":             "刈包 gua bao Taiwan pork belly bun",
    "scallion_pancake":    "蔥油餅 scallion pancake Taiwan",
    "oyster_omelette":     "蚵仔煎 oyster omelette Taiwan",
}

if __name__ == "__main__":
    for cls_name, query in TAIWANESE_CLASSES.items():
        save_dir = f"data/food_dataset/scraped/{cls_name}"
        os.makedirs(save_dir, exist_ok=True)
        print(f"Scraping {cls_name} ({query}) → {save_dir}")
        crawler = BingImageCrawler(
            feeder_threads=1, parser_threads=1, downloader_threads=4,
            storage={"root_dir": save_dir},
        )
        crawler.crawl(keyword=query, max_num=250, min_size=(100, 100))
        count = len([f for f in os.listdir(save_dir) if not f.startswith(".")])
        print(f"  ✓ {count} images saved")
