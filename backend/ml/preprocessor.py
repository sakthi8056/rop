"""
Image preprocessing pipeline for the AI model.
"""

import logging
import numpy as np
from PIL import Image
from config import get_settings

logger = logging.getLogger(__name__)


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Preprocess a retinal image for model inference.
    Returns a numpy array suitable for torch tensor conversion.
    """
    settings = get_settings()
    size = settings.MODEL_INPUT_SIZE

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        raise ValueError(f"Cannot open image for preprocessing: {e}")

    # Resize with center crop
    w, h = img.size
    scale = size / min(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop
    left = (new_w - size) // 2
    top = (new_h - size) // 2
    img = img.crop((left, top, left + size, top + size))

    # Convert to numpy and normalize (ImageNet stats)
    arr = np.array(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std

    # HWC -> CHW
    arr = arr.transpose(2, 0, 1)

    return arr


def preprocess_for_display(image_path: str, size: int = 224) -> np.ndarray:
    """
    Preprocess image and return the display-ready (non-normalized) version.
    Used for Grad-CAM overlay visualization.
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    scale = size / min(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - size) // 2
    top = (new_h - size) // 2
    img = img.crop((left, top, left + size, top + size))

    return np.array(img)
