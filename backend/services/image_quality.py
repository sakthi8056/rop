"""
Image quality assessment service.
Evaluates retinal images before AI inference.
"""

import logging
import os
import numpy as np
import cv2
from pathlib import Path
from typing import Tuple

from config import get_settings

logger = logging.getLogger(__name__)


class ImageQualityAssessor:
    """Assess retinal image quality for ROP screening suitability."""

    def __init__(self):
        self.settings = get_settings()

    def assess(self, image_path: str) -> dict:
        """
        Run all quality checks on an image.
        Returns a structured quality assessment result.
        """
        try:
            img = cv2.imread(image_path)
            if img is None and os.path.exists(image_path):
                # Fallback for Windows paths with non-ASCII or Unicode characters
                try:
                    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    img = None

            if img is None:
                return self._result(
                    status="UNGRADABLE",
                    score=0.0,
                    message="Image file could not be read. The file may be corrupted or in an unsupported format.",
                    checks={"readable": False},
                )

            checks = {}
            scores = []

            # 1. Resolution check
            h, w = int(img.shape[0]), int(img.shape[1])
            min_res = self.settings.MIN_IMAGE_RESOLUTION
            res_ok = bool(h >= min_res and w >= min_res)
            checks["resolution"] = {
                "passed": bool(res_ok),
                "width": int(w),
                "height": int(h),
                "minimum": int(min_res),
                "message": f"Resolution: {w}×{h}" + ("" if res_ok else f" — below minimum {min_res}×{min_res}"),
            }
            scores.append(1.0 if res_ok else 0.0)

            # 2. Color channels check
            channels_ok = bool(len(img.shape) == 3 and img.shape[2] == 3)
            checks["color_channels"] = {
                "passed": bool(channels_ok),
                "channels": int(img.shape[2]) if len(img.shape) == 3 else 1,
                "message": "3-channel RGB image" if channels_ok else "Image must be RGB (3 channels)",
            }
            scores.append(1.0 if channels_ok else 0.0)

            # Convert to grayscale for remaining checks
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if channels_ok else img

            # 3. Blur detection (Laplacian variance)
            laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            blur_ok = bool(laplacian_var >= self.settings.BLUR_THRESHOLD)
            blur_score = float(min(laplacian_var / (self.settings.BLUR_THRESHOLD * 3), 1.0))
            checks["blur"] = {
                "passed": bool(blur_ok),
                "laplacian_variance": round(float(laplacian_var), 2),
                "threshold": float(self.settings.BLUR_THRESHOLD),
                "message": "Image sharpness: acceptable" if blur_ok else "Image appears blurry or out of focus",
            }
            scores.append(blur_score)

            # 4. Brightness assessment
            mean_brightness = float(np.mean(gray))
            bright_ok = bool(self.settings.MIN_BRIGHTNESS <= mean_brightness <= self.settings.MAX_BRIGHTNESS)
            checks["brightness"] = {
                "passed": bool(bright_ok),
                "mean_value": round(float(mean_brightness), 2),
                "min": float(self.settings.MIN_BRIGHTNESS),
                "max": float(self.settings.MAX_BRIGHTNESS),
                "message": self._brightness_message(mean_brightness),
            }
            scores.append(1.0 if bright_ok else 0.3)

            # 5. Contrast check
            contrast = float(np.std(gray))
            contrast_ok = bool(contrast >= self.settings.MIN_CONTRAST)
            checks["contrast"] = {
                "passed": bool(contrast_ok),
                "std_deviation": round(float(contrast), 2),
                "threshold": float(self.settings.MIN_CONTRAST),
                "message": "Sufficient contrast" if contrast_ok else "Image has insufficient contrast",
            }
            scores.append(float(min(contrast / (self.settings.MIN_CONTRAST * 3), 1.0)))

            # 6. Aspect ratio check
            aspect_ratio = float(max(w, h) / max(min(w, h), 1))
            ratio_ok = bool(aspect_ratio <= 3.0)
            checks["aspect_ratio"] = {
                "passed": bool(ratio_ok),
                "ratio": round(float(aspect_ratio), 2),
                "max_allowed": 3.0,
                "message": f"Aspect ratio {aspect_ratio:.1f}:1" + ("" if ratio_ok else " — too extreme"),
            }
            scores.append(1.0 if ratio_ok else 0.2)

            # 7. Image artifacts / saturation check
            if channels_ok:
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                saturation_mean = float(np.mean(hsv[:, :, 1]))
                artifact_ok = bool(saturation_mean > 10)  # Not completely desaturated
                checks["artifacts"] = {
                    "passed": bool(artifact_ok),
                    "saturation_mean": round(float(saturation_mean), 2),
                    "message": "No severe artifacts detected" if artifact_ok else "Possible severe image artifacts or desaturation",
                }
                scores.append(1.0 if artifact_ok else 0.3)

            # Calculate overall score and status
            overall_score = float(sum(scores) / len(scores))
            all_critical_passed = bool(checks["resolution"]["passed"] and checks.get("color_channels", {}).get("passed", True))

            if not all_critical_passed:
                status = "UNGRADABLE"
                message = "Image does not meet minimum requirements for analysis."
            elif overall_score >= 0.7 and all(bool(c.get("passed", True)) for c in checks.values()):
                status = "ACCEPTABLE"
                message = "Image quality is acceptable for AI screening analysis."
            elif overall_score >= 0.5:
                status = "POOR"
                message = "Image quality is poor. Results may be unreliable. Consider recapturing the image."
            else:
                status = "UNGRADABLE"
                message = "Image quality is insufficient for reliable analysis. Please recapture with better lighting and focus."

            return self._result(status, overall_score, message, checks)

        except Exception as e:
            logger.error(f"Image quality assessment failed: {e}", exc_info=True)
            return self._result(
                status="UNGRADABLE",
                score=0.0,
                message=f"Quality assessment failed: could not process the image.",
                checks={"error": str(e)},
            )

    def _brightness_message(self, mean_val: float) -> str:
        if mean_val < self.settings.MIN_BRIGHTNESS:
            return "Image is too dark — insufficient illumination"
        elif mean_val > self.settings.MAX_BRIGHTNESS:
            return "Image is too bright — excessive illumination"
        return "Brightness level: acceptable"

    def _result(self, status: str, score: float, message: str, checks: dict) -> dict:
        return {
            "overall_status": status,
            "overall_score": round(score, 3),
            "is_acceptable": status == "ACCEPTABLE",
            "checks": checks,
            "message": message,
        }


# Singleton instance
_assessor = None


def get_quality_assessor() -> ImageQualityAssessor:
    global _assessor
    if _assessor is None:
        _assessor = ImageQualityAssessor()
    return _assessor
