"""
ROP Model Training Pipeline (EfficientNet-B0)
==============================================
A reproducible, production-grade training workflow for Retinopathy of
Prematurity (ROP) retinal fundus classification.

ETHICAL & CLINICAL DATASET REQUIREMENTS:
----------------------------------------
- Real ROP screening requires training on IRB-approved, clinically annotated
  retinal fundus image datasets collected by ophthalmologists.
- This script does NOT fabricate training data or claim medical validation.
- Output weights will be loaded by `backend/ml/model_loader.py`.

Dataset Directory Structure Expected:
-------------------------------------
data_dir/
  ├── train/
  │   ├── Normal/
  │   ├── Pre-Plus/
  │   └── Plus/
  └── val/
      ├── Normal/
      ├── Pre-Plus/
      └── Plus/
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rop_training")

CANONICAL_CLASSES = ["Normal", "Pre-Plus/Mild", "Plus Disease/Severe"]
CLASS_SYNONYMS = {
    "normal": "Normal",
    "0": "Normal",
    "pre-plus": "Pre-Plus/Mild",
    "pre_plus": "Pre-Plus/Mild",
    "preplus": "Pre-Plus/Mild",
    "mild": "Pre-Plus/Mild",
    "1": "Pre-Plus/Mild",
    "plus": "Plus Disease/Severe",
    "plus_disease": "Plus Disease/Severe",
    "severe": "Plus Disease/Severe",
    "2": "Plus Disease/Severe",
}


def match_class_name(dir_name: str) -> Optional[str]:
    """Map directory name to canonical 3-class ROP category."""
    clean = dir_name.strip().lower()
    return CLASS_SYNONYMS.get(clean)


def validate_dataset(data_dir: Path) -> Dict[str, any]:
    """
    Validate dataset structure, format integrity, and class balance.
    Returns summary statistics or raises ValueError if validation fails.
    """
    from PIL import Image

    if not data_dir.exists():
        raise FileNotFoundError(f"Dataset directory '{data_dir}' does not exist.")

    has_train = (data_dir / "train").is_dir()
    check_splits = []
    if has_train:
        check_splits.append("train")
        if (data_dir / "val").is_dir():
            check_splits.append("val")
        if (data_dir / "test").is_dir():
            check_splits.append("test")
    else:
        check_splits = ["."]

    stats = {
        "has_splits": has_train,
        "splits": {},
        "valid_images": 0,
        "corrupted_images": 0,
        "class_distribution": {},
    }

    for split in check_splits:
        split_dir = data_dir / split if split != "." else data_dir
        split_stats = {}

        for folder in split_dir.iterdir():
            if not folder.is_dir():
                continue

            canonical = match_class_name(folder.name)
            if not canonical:
                logger.warning(f"Skipping unrecognized folder: '{folder.name}'")
                continue

            images = []
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
                images.extend(list(folder.glob(ext)))

            valid_count = 0
            for img_path in images:
                try:
                    with Image.open(img_path) as img:
                        img.verify()
                    with Image.open(img_path) as img:
                        w, h = img.size
                        if w < 100 or h < 100:
                            logger.warning(f"Image {img_path.name} resolution too low ({w}x{h})")
                            stats["corrupted_images"] += 1
                            continue
                    valid_count += 1
                except Exception as e:
                    logger.warning(f"Corrupted image {img_path.name}: {e}")
                    stats["corrupted_images"] += 1

            split_stats[canonical] = valid_count
            stats["class_distribution"][canonical] = (
                stats["class_distribution"].get(canonical, 0) + valid_count
            )
            stats["valid_images"] += valid_count

        stats["splits"][split] = split_stats

    # Verify that all 3 canonical classes have samples
    missing_classes = [c for c in CANONICAL_CLASSES if stats["class_distribution"].get(c, 0) == 0]
    if missing_classes:
        logger.warning(
            f"Dataset is missing samples for: {missing_classes}. "
            "All 3 classes are needed for full ROP screening."
        )

    return stats


class ROPDataset:
    """
    ROP Retinal Fundus Dataset with explicit canonical class indexing:
    Class 0: Normal
    Class 1: Pre-Plus/Mild
    Class 2: Plus Disease/Severe
    """
    def __init__(self, root_dir: Path, transform=None):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.samples: List[Tuple[Path, int]] = []

        for folder in self.root_dir.iterdir():
            if not folder.is_dir():
                continue
            canonical = match_class_name(folder.name)
            if not canonical:
                logger.warning(f"Skipping folder with unrecognized class: '{folder.name}'")
                continue
            class_idx = CANONICAL_CLASSES.index(canonical)

            for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
                for img_path in folder.glob(ext):
                    self.samples.append((img_path, class_idx))

        if not self.samples:
            raise ValueError(f"No valid ROP image samples found in {self.root_dir}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, class_idx = self.samples[idx]
        from PIL import Image
        with Image.open(img_path) as img:
            image = img.convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, class_idx


def build_dataloaders(
    data_dir: Path,
    batch_size: int = 16,
    input_size: int = 224,
    num_workers: int = 0,
):
    """Build PyTorch DataLoaders with medical fundus image augmentations and canonical class indexing."""
    try:
        import torch
        from torchvision import transforms
    except ImportError:
        raise ImportError(
            "PyTorch and torchvision are required for training. "
            "Please install them via: pip install torch torchvision"
        )

    # Normalization matching preprocessor.py (ImageNet stats)
    normalize = transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )

    train_transforms = transforms.Compose([
        transforms.Resize(input_size + 32),
        transforms.RandomCrop(input_size),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        normalize,
    ])

    val_transforms = transforms.Compose([
        transforms.Resize(input_size),
        transforms.CenterCrop(input_size),
        transforms.ToTensor(),
        normalize,
    ])

    has_explicit_splits = (data_dir / "train").is_dir() and (data_dir / "val").is_dir()

    if has_explicit_splits:
        train_dataset = ROPDataset(data_dir / "train", transform=train_transforms)
        val_dataset = ROPDataset(data_dir / "val", transform=val_transforms)
    else:
        full_dataset = ROPDataset(data_dir, transform=train_transforms)
        val_size = max(int(0.2 * len(full_dataset)), 1)
        train_size = len(full_dataset) - val_size
        train_dataset, val_dataset = torch.utils.data.random_split(
            full_dataset, [train_size, val_size]
        )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )

    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    return train_loader, val_loader


def create_model(num_classes: int = 3, pretrained: bool = True):
    """Instantiate EfficientNet-B0 matching backend/ml/model_loader.py."""
    try:
        import torch
        import torchvision.models as models
    except ImportError:
        raise ImportError("PyTorch and torchvision must be installed.")

    try:
        weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        model = models.efficientnet_b0(weights=weights)
    except Exception as e:
        logger.warning(f"Could not load online pretrained weights ({e}). Initializing without pretrained weights.")
        model = models.efficientnet_b0(weights=None)

    # Replace final classifier layer
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, num_classes)

    return model


def train_epoch(model, loader, criterion, optimizer, device):
    """Run one training epoch."""
    import torch

    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for inputs, labels in loader:
        inputs = inputs.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * inputs.size(0)
        _, preds = torch.max(outputs, 1)
        correct += torch.sum(preds == labels.data).item()
        total += inputs.size(0)

    epoch_loss = running_loss / max(total, 1)
    epoch_acc = correct / max(total, 1)
    return epoch_loss, epoch_acc


def validate_epoch(model, loader, criterion, device):
    """Run validation and compute loss & accuracy."""
    import torch

    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    all_preds = []
    all_targets = []

    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * inputs.size(0)
            _, preds = torch.max(outputs, 1)
            correct += torch.sum(preds == labels.data).item()
            total += inputs.size(0)

            all_preds.extend(preds.cpu().numpy().tolist())
            all_targets.extend(labels.cpu().numpy().tolist())

    epoch_loss = running_loss / max(total, 1)
    epoch_acc = correct / max(total, 1)
    return epoch_loss, epoch_acc, all_preds, all_targets


def train_pipeline(
    data_dir: str,
    output_path: str = "backend/ml/weights/rop_model.pth",
    epochs: int = 25,
    batch_size: int = 16,
    lr: float = 1e-4,
    device_str: Optional[str] = None,
):
    """Full ROP model training and checkpoint saving workflow."""
    import torch
    import torch.nn as nn
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR

    data_path = Path(data_dir)
    logger.info(f"Validating dataset at: {data_path.resolve()}")
    stats = validate_dataset(data_path)
    logger.info(f"Dataset stats: {stats['valid_images']} valid images, classes: {stats['class_distribution']}")

    if stats["valid_images"] == 0:
        raise ValueError("No valid training images found in dataset directory.")

    device = torch.device(
        device_str or ("cuda" if torch.cuda.is_available() else "cpu")
    )
    logger.info(f"Training using compute device: {device}")

    train_loader, val_loader = build_dataloaders(data_path, batch_size=batch_size)
    model = create_model(num_classes=3, pretrained=True).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    best_epoch = 0

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    history = []

    for epoch in range(1, epochs + 1):
        t_loss, t_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        v_loss, v_acc, _, _ = validate_epoch(model, val_loader, criterion, device)
        scheduler.step()

        logger.info(
            f"Epoch [{epoch:02d}/{epochs:02d}] "
            f"Train Loss: {t_loss:.4f} | Train Acc: {t_acc*100:.1f}% | "
            f"Val Loss: {v_loss:.4f} | Val Acc: {v_acc*100:.1f}%"
        )

        history.append({
            "epoch": epoch,
            "train_loss": round(t_loss, 4),
            "train_acc": round(t_acc, 4),
            "val_loss": round(v_loss, 4),
            "val_acc": round(v_acc, 4),
        })

        if v_acc > best_val_acc or epoch == 1:
            best_val_acc = v_acc
            best_epoch = epoch
            torch.save(model.state_dict(), str(out_file))
            logger.info(f"  --> Saved new best checkpoint to {out_file} (Val Acc: {v_acc*100:.1f}%)")

    total_time = time.time() - start_time
    logger.info(f"Training completed in {total_time:.1f}s. Best Epoch: {best_epoch} (Val Acc: {best_val_acc*100:.1f}%)")

    # Save training metadata JSON alongside model weights
    meta_path = out_file.parent / "model_metadata.json"
    metadata = {
        "model_architecture": "EfficientNet-B0",
        "num_classes": 3,
        "class_labels": CANONICAL_CLASSES,
        "input_size": 224,
        "training_epochs": epochs,
        "best_epoch": best_epoch,
        "best_val_accuracy": round(best_val_acc, 4),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_history": history,
        "clinical_disclaimer": (
            "Research Prototype Model: Clinical diagnostic validation and regulatory "
            "approval (e.g. FDA/CE/CDSCO) are required before deployment in live care."
        ),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved model metadata to {meta_path}")
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Train an EfficientNet-B0 model for ROP screening classification."
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="Path to training dataset folder",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default="backend/ml/weights/rop_model.pth",
        help="Target filepath for saving the trained weights (.pth)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=25,
        help="Number of training epochs (default: 25)",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Batch size (default: 16)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=1e-4,
        help="Learning rate (default: 0.0001)",
    )
    parser.add_argument(
        "--validate_only",
        action="store_true",
        help="Only validate dataset integrity and distribution without starting training",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Execution device ('cuda' or 'cpu')",
    )

    args = parser.parse_args()

    if args.validate_only:
        stats = validate_dataset(Path(args.data_dir))
        print("\n--- Dataset Validation Report ---")
        print(f"Total Valid Images: {stats['valid_images']}")
        print(f"Corrupted/Low-Res:  {stats['corrupted_images']}")
        print(f"Class Distribution: {stats['class_distribution']}")
        print("---------------------------------")
        return

    train_pipeline(
        data_dir=args.data_dir,
        output_path=args.output_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device_str=args.device,
    )


if __name__ == "__main__":
    main()
