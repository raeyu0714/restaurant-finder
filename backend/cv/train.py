"""
Fine-tune the last classification layer of nateraw/food (ViT-B/16) to 110 classes
(Food-101 + 9 Taiwanese foods).  Only the new head is trained — backbone is frozen.

Resource requirements:
  Training VRAM: ~2–3 GB   |   Training RAM: ~4 GB
  Training time: ~10–20 min on NVIDIA GPU (backbone frozen, only head updated)
  Model output: backend/cv/models/food_vit/ (~330 MB)

Usage (run from project root, or copy this script into Google Colab):
    pip install torch torchvision transformers datasets
    python backend/cv/train.py
"""
import json, random, os
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from transformers import AutoImageProcessor, AutoModelForImageClassification

BASE_MODEL  = "nateraw/food"
DATA_DIR    = Path("data/food_dataset")
SAVE_DIR    = Path("backend/cv/models/food_vit")
EPOCHS      = 15
BATCH_SIZE  = 32
LR          = 1e-3
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Device: {DEVICE}")
print(f"Data:   {DATA_DIR}")
print(f"Save:   {SAVE_DIR}")

# ── Load pretrained ViT-B/16 (nateraw/food = Food-101 fine-tuned) ──────────────
print("Loading nateraw/food…")
extractor = AutoImageProcessor.from_pretrained(BASE_MODEL)
model     = AutoModelForImageClassification.from_pretrained(BASE_MODEL)

# ── Freeze entire backbone — only train the new head ──────────────────────────
for param in model.parameters():
    param.requires_grad = False

# ── Replace classification head: 768 → N classes ─────────────────────────────
num_features = model.classifier.in_features
model.classifier = nn.Linear(num_features, 1)   # placeholder, resized after dataset loaded

# ── Dataset ───────────────────────────────────────────────────────────────────
mean = extractor.image_mean
std  = extractor.image_std

train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=mean, std=std),
])
val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=mean, std=std),
])

train_ds = datasets.ImageFolder(DATA_DIR / "train", transform=train_transform)
val_ds   = datasets.ImageFolder(DATA_DIR / "val",   transform=val_transform)
num_classes = len(train_ds.classes)
print(f"Classes: {num_classes}  |  train: {len(train_ds)}  |  val: {len(val_ds)}")

# ── Resize head to actual number of classes ───────────────────────────────────
model.classifier = nn.Linear(num_features, num_classes)
model.config.num_labels = num_classes
model.to(DEVICE)

# ── Save class→idx mapping for inference ──────────────────────────────────────
SAVE_DIR.mkdir(parents=True, exist_ok=True)
(SAVE_DIR / "class_to_idx.json").write_text(
    json.dumps(train_ds.class_to_idx, ensure_ascii=False, indent=2)
)

train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=4, pin_memory=True)
val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

optimizer = torch.optim.Adam(model.classifier.parameters(), lr=LR)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
criterion = nn.CrossEntropyLoss()
best_acc  = 0.0

for epoch in range(EPOCHS):
    # Train
    model.train()
    train_loss = 0.0
    for imgs, labels in train_dl:
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        loss = criterion(model(imgs).logits, labels)
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
    scheduler.step()

    # Validate
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for imgs, labels in val_dl:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            preds = model(imgs).logits.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total   += labels.size(0)
    acc = correct / total
    avg_loss = train_loss / len(train_dl)
    print(f"Epoch {epoch+1:2d}/{EPOCHS}  loss={avg_loss:.4f}  val_acc={acc:.3f}")

    if acc > best_acc:
        best_acc = acc
        model.save_pretrained(SAVE_DIR)
        extractor.save_pretrained(SAVE_DIR)
        print(f"  → Saved  (best: {best_acc:.3f})")

print(f"\n✓ Training done.  Best val accuracy: {best_acc:.3f}")
print(f"  Model saved to: {SAVE_DIR}")
print(f"  class_to_idx:   {SAVE_DIR}/class_to_idx.json")
