"""
Run once offline to prepare the training dataset.
Downloads Food-101 from HuggingFace datasets, merges with scraped Taiwanese images,
splits train/val (80/20).

Output: data/food_dataset/train/<class>/ and data/food_dataset/val/<class>/

Usage (from project root):
    pip install datasets icrawler
    python backend/cv/scrape_data.py      # scrape Taiwanese images first
    python backend/cv/prepare_dataset.py  # then prepare dataset
"""
import os, shutil, random
from pathlib import Path

SCRAPED_DIR = Path("data/food_dataset/scraped")
OUT_DIR     = Path("data/food_dataset")
FOOD101_DIR = Path("data/food-101/images")   # manual download fallback


def split_and_copy(src_dir: Path, class_name: str, ratio: float = 0.8) -> int:
    imgs = (list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.jpeg")) +
            list(src_dir.glob("*.png")) + list(src_dir.glob("*.webp")))
    if not imgs:
        print(f"  ⚠ No images found in {src_dir}")
        return 0
    random.shuffle(imgs)
    split = int(len(imgs) * ratio)
    for dest, files in [("train", imgs[:split]), ("val", imgs[split:])]:
        d = OUT_DIR / dest / class_name
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy(f, d / f.name)
    return len(imgs)


def prepare_food101_from_hf():
    """Download Food-101 via HuggingFace datasets (requires: pip install datasets)."""
    try:
        from datasets import load_dataset
        import PIL.Image
    except ImportError:
        print("datasets/PIL not found — falling back to manual Food-101 directory")
        return False

    print("Downloading Food-101 from HuggingFace (may take a few minutes)…")
    ds = load_dataset("food101", split="train+validation", trust_remote_code=True)

    for item in ds:
        label = ds.features["label"].int2str(item["label"])
        for split_name in ("train", "val"):
            pass  # handled below via split

    # Simpler: split 80/20 ourselves
    all_items = list(ds)
    random.shuffle(all_items)
    split = int(len(all_items) * 0.8)
    splits = {"train": all_items[:split], "val": all_items[split:]}

    for split_name, items in splits.items():
        for item in items:
            label = ds.features["label"].int2str(item["label"])
            dest  = OUT_DIR / split_name / label
            dest.mkdir(parents=True, exist_ok=True)
            img_path = dest / f"{hash(str(item['image']))}.jpg"
            if not img_path.exists():
                item["image"].convert("RGB").save(img_path, "JPEG")

    print(f"  ✓ Food-101: {len(all_items)} images split into train/val")
    return True


if __name__ == "__main__":
    random.seed(42)

    # 1. Food-101
    if FOOD101_DIR.exists():
        print("Using local Food-101 directory…")
        for cls_dir in sorted(FOOD101_DIR.iterdir()):
            if cls_dir.is_dir():
                n = split_and_copy(cls_dir, cls_dir.name)
                print(f"  food-101 → {cls_dir.name}: {n} images")
    else:
        ok = prepare_food101_from_hf()
        if not ok:
            print(f"ERROR: Food-101 not found at {FOOD101_DIR}.")
            print("Download from https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/")
            print("and extract to data/food-101/images/<class>/<img>.jpg")
            raise SystemExit(1)

    # 2. Taiwanese classes (scraped)
    if SCRAPED_DIR.exists():
        for cls_dir in sorted(SCRAPED_DIR.iterdir()):
            if cls_dir.is_dir():
                n = split_and_copy(cls_dir, cls_dir.name)
                print(f"  taiwanese → {cls_dir.name}: {n} images")
    else:
        print(f"WARNING: {SCRAPED_DIR} not found — skipping Taiwanese classes.")
        print("Run backend/cv/scrape_data.py first.")

    # Count final classes
    train_classes = sorted(p.name for p in (OUT_DIR / "train").iterdir() if p.is_dir())
    print(f"\n✓ Dataset ready: {len(train_classes)} classes in {OUT_DIR}")
    print(f"  train: {sum(1 for _ in (OUT_DIR/'train').rglob('*.*'))} images")
    print(f"  val:   {sum(1 for _ in (OUT_DIR/'val').rglob('*.*'))} images")
