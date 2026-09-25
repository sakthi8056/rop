"""
AI inference engine for ROP screening.
Handles both real model inference and clearly labeled demo mode.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from config import get_settings
from ml.model_loader import get_model
from ml.preprocessor import preprocess_image

logger = logging.getLogger(__name__)


class AIEngine:
    """ROP screening AI inference engine."""

    def __init__(self):
        self.settings = get_settings()

    def analyze(self, image_path: str) -> dict:
        """
        Run AI inference on a retinal image.
        Returns structured result with clear demo/real labeling.
        """
        model, is_available = get_model()

        if not is_available:
            return self._demo_inference(image_path)

        return self._real_inference(model, image_path)

    def _real_inference(self, model, image_path: str) -> dict:
        """Run actual model inference."""
        try:
            import torch

            # Preprocess
            img_array = preprocess_image(image_path)
            input_tensor = torch.FloatTensor(img_array).unsqueeze(0)

            # Inference
            with torch.no_grad():
                outputs = model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                probs = probabilities.squeeze().numpy()
                predicted_class = int(np.argmax(probs))

            class_labels = self.settings.MODEL_CLASS_LABELS
            classification = class_labels[predicted_class]
            confidence = float(probs[predicted_class])

            prob_dict = {
                label: round(float(probs[i]), 4)
                for i, label in enumerate(class_labels)
            }

            return {
                "classification": classification,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "predicted_class_index": predicted_class,
                "is_demo": False,
                "model_name": self.settings.MODEL_NAME,
                "model_version": self.settings.MODEL_VERSION,
                "status": "completed",
                "screening_limitations": (
                    "This AI screening result is provided by a research prototype model. "
                    "It does not constitute a confirmed diagnosis and must be reviewed by "
                    "a qualified ophthalmologist."
                ),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Model inference failed: {e}", exc_info=True)
            return {
                "classification": None,
                "confidence": None,
                "probabilities": None,
                "is_demo": False,
                "model_name": self.settings.MODEL_NAME,
                "model_version": self.settings.MODEL_VERSION,
                "status": "failed",
                "error": str(e),
                "screening_limitations": (
                    "AI analysis could not be completed due to a technical error. "
                    "Manual specialist review is required."
                ),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

    def _demo_inference(self, image_path: str) -> dict:
        """
        Generate clearly labeled demonstration output.
        Uses FIXED synthetic values — never random numbers or fabricated confidence.
        """
        logger.info("Running DEMO MODE inference (no trained model loaded)")

        class_labels = self.settings.MODEL_CLASS_LABELS

        # Fixed demo probabilities — clearly not from a real model
        demo_probs = {
            class_labels[0]: 0.00,  # Normal
            class_labels[1]: 0.00,  # Pre-Plus/Mild
            class_labels[2]: 0.00,  # Plus Disease/Severe
        }

        return {
            "classification": "DEMO — No Real Model Loaded",
            "confidence": None,
            "probabilities": demo_probs,
            "predicted_class_index": None,
            "is_demo": True,
            "model_name": f"{self.settings.MODEL_NAME} [DEMO]",
            "model_version": self.settings.MODEL_VERSION,
            "status": "demo",
            "screening_limitations": (
                "⚠️ DEMO MODE: No trained AI model is loaded. "
                "This output is a synthetic demonstration and has NO clinical validity. "
                "Do not use this result for any medical decision. "
                "To enable real AI screening, install a validated model file."
            ),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton instance
_engine = None


def get_ai_engine() -> AIEngine:
    global _engine
    if _engine is None:
        _engine = AIEngine()
    return _engine
