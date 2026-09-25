"""
Dynamic model loader for ROP screening.
Supports loading trained EfficientNet-B0 weights and graceful fallback.
"""

import logging
from pathlib import Path
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)

# Cached model instance
_model = None
_model_loaded = False


def load_model():
    """
    Load the ROP screening model from weights file.
    Returns (model, True) on success, (None, False) on failure.
    """
    global _model, _model_loaded

    if _model_loaded and _model is not None:
        return _model, True

    settings = get_settings()
    weights_path = settings.model_weights_path

    if not weights_path.exists():
        logger.info(f"No model weights at {weights_path}. Running in DEMO MODE.")
        _model = None
        _model_loaded = False
        return None, False

    try:
        import torch
        import torchvision.models as models

        logger.info(f"Loading model weights from {weights_path}")

        # Create EfficientNet-B0 architecture
        model = models.efficientnet_b0(weights=None)
        num_classes = settings.MODEL_NUM_CLASSES

        # Replace classifier head
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)

        # Load trained weights
        state_dict = torch.load(str(weights_path), map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
        model.eval()

        _model = model
        _model_loaded = True
        logger.info("Model loaded successfully")
        return model, True

    except ImportError:
        logger.warning("PyTorch not installed. Running in DEMO MODE.")
        _model = None
        _model_loaded = False
        return None, False

    except Exception as e:
        logger.error(f"Failed to load model: {e}", exc_info=True)
        _model = None
        _model_loaded = False
        return None, False


def get_model():
    """Get the cached model instance."""
    return load_model()


def reset_model():
    """Force reload of the model (e.g., after replacing weights file)."""
    global _model, _model_loaded
    _model = None
    _model_loaded = False
