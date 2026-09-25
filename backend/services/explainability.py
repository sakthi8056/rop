"""
Explainability module: Grad-CAM heatmap generation.
"""

import logging
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional

from config import get_settings
from ml.model_loader import get_model
from ml.preprocessor import preprocess_image, preprocess_for_display

logger = logging.getLogger(__name__)


class ExplainabilityService:
    """Generate Grad-CAM or demo heatmaps for model explainability."""

    def __init__(self):
        self.settings = get_settings()

    def generate(
        self, image_path: str, session_id: str, image_id: str, predicted_class: Optional[int] = None
    ) -> dict:
        """
        Generate explainability visualization.
        Returns paths to heatmap and overlay images.
        """
        model, is_available = get_model()

        if not is_available:
            return self._generate_demo_heatmap(image_path, session_id, image_id)

        return self._generate_gradcam(model, image_path, session_id, image_id, predicted_class)

    def _generate_gradcam(
        self, model, image_path: str, session_id: str, image_id: str, predicted_class: Optional[int]
    ) -> dict:
        """Generate real Grad-CAM heatmap."""
        try:
            import torch
            from pytorch_grad_cam import GradCAM
            from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
            from pytorch_grad_cam.utils.image import show_cam_on_image

            # Prepare input
            img_array = preprocess_image(image_path)
            input_tensor = torch.FloatTensor(img_array).unsqueeze(0)

            # Display image (non-normalized)
            display_img = preprocess_for_display(image_path) / 255.0

            # Target layer: last conv block of EfficientNet
            target_layers = [model.features[-1]]

            # Generate CAM
            cam = GradCAM(model=model, target_layers=target_layers)
            targets = [ClassifierOutputTarget(predicted_class)] if predicted_class is not None else None
            grayscale_cam = cam(input_tensor=input_tensor, targets=targets)
            grayscale_cam = grayscale_cam[0, :]

            # Create overlay
            overlay = show_cam_on_image(display_img, grayscale_cam, use_rgb=True)

            # Create colored heatmap
            heatmap_colored = cv2.applyColorMap(
                np.uint8(255 * grayscale_cam), cv2.COLORMAP_JET
            )
            heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

            # Save images
            heatmap_path, overlay_path = self._save_visualizations(
                session_id, image_id, heatmap_colored, overlay
            )

            return {
                "heatmap_url": f"/uploads/{Path(heatmap_path).name}",
                "overlay_url": f"/uploads/{Path(overlay_path).name}",
                "is_demo": False,
                "explanation": (
                    "This Grad-CAM heatmap highlights the image regions that most influenced "
                    "the AI model's screening output. Warmer colors (red/yellow) indicate "
                    "higher attention. This visualization aids interpretation but does not "
                    "independently establish a diagnosis."
                ),
                "status": "generated",
            }

        except ImportError:
            logger.warning("pytorch-grad-cam not available, falling back to demo visualization")
            return self._generate_demo_heatmap(image_path, session_id, image_id)

        except Exception as e:
            logger.error(f"Grad-CAM generation failed: {e}", exc_info=True)
            return {
                "heatmap_url": None,
                "overlay_url": None,
                "is_demo": False,
                "explanation": "Explainability visualization could not be generated due to a technical error.",
                "status": "failed",
            }

    def _generate_demo_heatmap(self, image_path: str, session_id: str, image_id: str) -> dict:
        """
        Generate a clearly labeled synthetic demo heatmap.
        Uses a simple Gaussian blob at center — obviously not from a real model.
        """
        try:
            display_img = preprocess_for_display(image_path, size=224)
            size = display_img.shape[0]

            # Create a simple Gaussian centered heatmap
            x = np.linspace(-1, 1, size)
            y = np.linspace(-1, 1, size)
            xx, yy = np.meshgrid(x, y)
            gaussian = np.exp(-(xx ** 2 + yy ** 2) / 0.5)
            gaussian = (gaussian / gaussian.max()).astype(np.float32)

            # Colored heatmap
            heatmap_colored = cv2.applyColorMap(
                np.uint8(255 * gaussian), cv2.COLORMAP_JET
            )
            heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

            # Overlay
            overlay = (display_img * 0.6 + heatmap_colored * 0.4).astype(np.uint8)

            # Add "DEMO" text
            overlay_bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            cv2.putText(
                overlay_bgr, "DEMO", (10, size - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
            )
            overlay = cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)

            heatmap_path, overlay_path = self._save_visualizations(
                session_id, image_id, heatmap_colored, overlay
            )

            return {
                "heatmap_url": f"/uploads/{Path(heatmap_path).name}",
                "overlay_url": f"/uploads/{Path(overlay_path).name}",
                "is_demo": True,
                "explanation": (
                    "⚠️ DEMO VISUALIZATION: This is a synthetic demonstration heatmap. "
                    "It does NOT represent actual AI model attention. "
                    "No trained model is loaded."
                ),
                "status": "demo",
            }

        except Exception as e:
            logger.error(f"Demo heatmap generation failed: {e}")
            return {
                "heatmap_url": None,
                "overlay_url": None,
                "is_demo": True,
                "explanation": "Visualization could not be generated.",
                "status": "failed",
            }

    def _save_visualizations(
        self, session_id: str, image_id: str, heatmap: np.ndarray, overlay: np.ndarray
    ) -> tuple:
        """Save heatmap and overlay images to uploads directory."""
        uploads_dir = self.settings.UPLOADS_DIR

        heatmap_filename = f"{session_id}_{image_id}_heatmap.png"
        overlay_filename = f"{session_id}_{image_id}_overlay.png"

        heatmap_path = os.path.join(uploads_dir, heatmap_filename)
        overlay_path = os.path.join(uploads_dir, overlay_filename)

        from PIL import Image as PILImage

        PILImage.fromarray(heatmap).save(heatmap_path)
        PILImage.fromarray(overlay).save(overlay_path)

        return heatmap_path, overlay_path


# Singleton
_service = None


def get_explainability_service() -> ExplainabilityService:
    global _service
    if _service is None:
        _service = ExplainabilityService()
    return _service
