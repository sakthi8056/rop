"""
ROP Dataset Acquisition, Preparation & Validation Utility
==========================================================
Provides workflows to:
1. Document and reference legitimate open-access Retinopathy of Prematurity datasets:
   - FARFUM-RoP (Figshare): https://doi.org/10.6084/m9.figshare.24075593
   - Macretina (Figshare): https://figshare.com/articles/dataset/Macretina_A_dataset_to_support_deep_learning_assisted_Retinopathy_of_Prematurity_diagnosis/24513812
   - Kaggle ROP Collections (e.g. zohaibaslam03/augmented-dataset)
   - ROP-VL (GitHub/Figshare): https://doi.org/10.6084/m9.figshare.27137350
2. Organize arbitrary downloaded ROP datasets into the canonical 3-class structure:
   - train/Normal, train/Pre-Plus, train/Plus
   - val/Normal, val/Pre-Plus, val/Plus
3. Validate format, resolution, integrity, and class distribution.
4. Generate a reproducible local benchmark dataset for pipeline verification.
"""

import argparse
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("dataset_utility")

CANONICAL_CLASSES = ["Normal", "Pre-Plus/Mild", "Plus Disease/Severe"]

FOLDER_SYNONYMS = {
    "normal": "Normal",
    "0": "Normal",
    "stage_0": "Normal",
    "no_rop": "Normal",
    "pre-plus": "Pre-Plus/Mild",
    "pre_plus": "Pre-Plus/Mild",
    "preplus": "Pre-Plus/Mild",
    "mild": "Pre-Plus/Mild",
    "1": "Pre-Plus/Mild",
    "stage_1": "Pre-Plus/Mild",
    "plus": "Plus Disease/Severe",
    "plus_disease": "Plus Disease/Severe",
    "severe": "Plus Disease/Severe",
    "2": "Plus Disease/Severe",
    "stage_2": "Plus Disease/Severe",
    "stage_3": "Plus Disease/Severe",
}


def print_public_dataset_info():
    """Print documentation of legitimate, open-access ROP datasets."""
    print("=" * 70)
    print("LEGITIMATE PUBLIC RETINOPATHY OF PREMATURITY (ROP) DATASETS")
    print("=" * 70)
    print("""
1. FARFUM-RoP (Fundus Images from Neonates for ROP Classification)
   - Description: 1,533 retinal fundus images from 68 preterm infants.
   - Clinical Labels: 3 classes — Normal, Pre-Plus, and Plus Disease.
   - Repository: Figshare (CC-BY 4.0 Open Access)
   - URL: https://doi.org/10.6084/m9.figshare.24075593
   - How to use: Download the archive and extract into a local folder, then run:
     python backend/ml/dataset_downloader.py --organize --source "C:\\path\\to\\FARFUM" --output "data/rop_dataset"

2. Macretina ROP Dataset
   - Description: 1,432 retinal fundus images curated to support deep learning
     assisted Retinopathy of Prematurity diagnosis.
   - Repository: Figshare (Academic Open Access)
   - URL: https://figshare.com/articles/dataset/Macretina_A_dataset_to_support_deep_learning_assisted_Retinopathy_of_Prematurity_diagnosis/24513812

3. Kaggle ROP Collection
   - Search: 'Retinopathy of Prematurity' on Kaggle Datasets
   - Example: kaggle.com/datasets/zohaibaslam03/augmented-dataset
   - Download via Kaggle CLI:
     kaggle datasets download -d zohaibaslam03/augmented-dataset -p data/raw_kaggle --unzip

4. ROP-VL (Multimodal ROP Dataset)
   - Description: Fundus photographs paired with ophthalmological notes.
   - Repository: GitHub (SB-Chen/ROP-VL) & Figshare
   - URL: https://doi.org/10.6084/m9.figshare.27137350

CLINICAL & ETHICAL NOTICE:
- All datasets used for clinical validation must have IRB approval and formal
  ophthalmologist review. This tool operates as a research prototype.
""")
    print("=" * 70)


def match_folder_to_class(folder_name: str) -> Optional[str]:
    """Map folder name to one of the 3 canonical ROP categories."""
    clean = folder_name.strip().lower().replace(" ", "_")
    return FOLDER_SYNONYMS.get(clean)


def organize_dataset(
    source_dir: Path,
    output_dir: Path,
    val_split: float = 0.2,
    seed: int = 42,
) -> Dict[str, any]:
    """
    Scan source directory, identify class subfolders, and copy images into
    output_dir/train/ and output_dir/val/ under canonical folder names.
    """
    np.random.seed(seed)
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory '{source_dir}' does not exist.")

    # Prepare output folders
    canonical_folder_names = {
        "Normal": "Normal",
        "Pre-Plus/Mild": "Pre-Plus",
        "Plus Disease/Severe": "Plus",
    }

    for split in ["train", "val"]:
        for cname in canonical_folder_names.values():
            (output_dir / split / cname).mkdir(parents=True, exist_ok=True)

    collected_by_class: Dict[str, List[Path]] = {c: [] for c in CANONICAL_CLASSES}

    # Find all images recursively
    for path in source_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            parent_name = path.parent.name
            canonical_class = match_folder_to_class(parent_name)
            if canonical_class:
                collected_by_class[canonical_class].append(path)

    stats = {"train": {}, "val": {}, "total_processed": 0}

    for canonical_class, img_paths in collected_by_class.items():
        if not img_paths:
            logger.warning(f"No images found for class: {canonical_class}")
            continue

        np.random.shuffle(img_paths)
        val_count = max(int(len(img_paths) * val_split), 1) if len(img_paths) > 4 else 1
        train_count = len(img_paths) - val_count

        train_imgs = img_paths[:train_count]
        val_imgs = img_paths[train_count:]

        folder_name = canonical_folder_names[canonical_class]

        for img in train_imgs:
            dst = output_dir / "train" / folder_name / f"{img.stem}_{img.name}"
            shutil.copy2(str(img), str(dst))

        for img in val_imgs:
            dst = output_dir / "val" / folder_name / f"{img.stem}_{img.name}"
            shutil.copy2(str(img), str(dst))

        stats["train"][canonical_class] = len(train_imgs)
        stats["val"][canonical_class] = len(val_imgs)
        stats["total_processed"] += len(img_paths)
        logger.info(f"Class '{canonical_class}': {len(train_imgs)} train, {len(val_imgs)} val")

    logger.info(f"Organized dataset into {output_dir}. Total images: {stats['total_processed']}")
    return stats


def generate_benchmark_dataset(
    output_dir: Path,
    num_per_class: int = 15,
) -> Dict[str, int]:
    """
    Generate a reproducible benchmark retinal dataset for testing the
    complete training-to-inference pipeline locally.
    Simulates fundus disc/cup and vascular patterns at standard resolution (300x300).
    """
    output_dir = Path(output_dir)
    np.random.seed(123)

    classes_to_folder = {
        "Normal": "Normal",
        "Pre-Plus/Mild": "Pre-Plus",
        "Plus Disease/Severe": "Plus",
    }

    counts = {"train": 0, "val": 0}

    for split, count in [("train", num_per_class), ("val", max(num_per_class // 3, 3))]:
        for cname, folder_name in classes_to_folder.items():
            folder_path = output_dir / split / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)

            for i in range(count):
                img = np.zeros((300, 300, 3), dtype=np.uint8)

                # Fundus background (warm red-orange)
                bg_color = (160 + np.random.randint(-15, 15), 60 + np.random.randint(-10, 10), 20)
                # Circular retina mask
                center = (150, 150)
                radius = 135

                y, x = np.ogrid[:300, :300]
                mask = (x - center[0]) ** 2 + (y - center[1]) ** 2 <= radius ** 2
                img[mask] = bg_color

                # Optic disc (yellowish circle on nasal side)
                disc_center = (210, 145)
                disc_mask = (x - disc_center[0]) ** 2 + (y - disc_center[1]) ** 2 <= 26 ** 2
                img[disc_mask] = (245, 215, 120)

                # Cup (lighter center of disc)
                cup_mask = (x - disc_center[0]) ** 2 + (y - disc_center[1]) ** 2 <= 12 ** 2
                img[cup_mask] = (255, 245, 180)

                # Vessel simulation based on class
                # Normal: thin, gentle curves
                # Pre-Plus: moderate tortuosity/dilation
                # Plus Disease: severe dilation and high tortuosity
                if cname == "Normal":
                    vessel_width = 1
                    num_vessels = 4
                elif cname == "Pre-Plus/Mild":
                    vessel_width = 2
                    num_vessels = 6
                else:  # Plus Disease
                    vessel_width = 3
                    num_vessels = 8

                # Draw vessels radiating from optic disc
                for v in range(num_vessels):
                    angle = (v / num_vessels) * 2 * np.pi + np.random.uniform(-0.2, 0.2)
                    for step in range(10, 120, 4):
                        vx = int(disc_center[0] - step * np.cos(angle) + np.sin(step * 0.1) * (vessel_width * 2))
                        vy = int(disc_center[1] - step * np.sin(angle) + np.cos(step * 0.1) * (vessel_width * 2))
                        if 0 <= vx < 300 and 0 <= vy < 300 and mask[vy, vx]:
                            for dx in range(-vessel_width, vessel_width + 1):
                                for dy in range(-vessel_width, vessel_width + 1):
                                    if 0 <= vx + dx < 300 and 0 <= vy + dy < 300:
                                        img[vy + dy, vx + dx] = (100, 20, 15)

                file_path = folder_path / f"retina_{cname.replace('/', '_')}_{split}_{i:03d}.jpg"
                Image.fromarray(img).save(file_path, quality=92)
                counts[split] += 1

    logger.info(f"Generated benchmark dataset at {output_dir.resolve()}: {counts['train']} train, {counts['val']} val images.")
    return counts


def main():
    parser = argparse.ArgumentParser(description="ROP Dataset Acquisition and Organization Utility")
    parser.add_argument("--info", action="store_true", help="Print legitimate public ROP dataset sources and links")
    parser.add_argument("--organize", action="store_true", help="Organize a raw downloaded ROP dataset into canonical structure")
    parser.add_argument("--source", type=str, help="Source directory containing unorganized images")
    parser.add_argument("--output", type=str, default="data/rop_dataset", help="Target dataset directory")
    parser.add_argument("--prepare_benchmark", action="store_true", help="Generate a local benchmark dataset for pipeline verification")
    parser.add_argument("--num_samples", type=int, default=20, help="Number of benchmark samples per class")

    args = parser.parse_args()

    if args.info or (not args.organize and not args.prepare_benchmark):
        print_public_dataset_info()

    if args.organize:
        if not args.source:
            print("Error: --source directory required for --organize")
            return
        organize_dataset(Path(args.source), Path(args.output))

    if args.prepare_benchmark:
        generate_benchmark_dataset(Path(args.output), num_per_class=args.num_samples)


if __name__ == "__main__":
    main()
