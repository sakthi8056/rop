import os
import cv2
import numpy as np
import pytest
from PIL import Image
from services.image_quality import get_quality_assessor


def test_assess_image_quality_blank_image(tmp_path):
    assessor = get_quality_assessor()

    # Save a black image to a temporary file using PIL (immune to Windows Unicode path issues)
    blank_image = np.zeros((300, 300, 3), dtype=np.uint8)
    image_path = str(tmp_path / "blank.jpg")
    Image.fromarray(blank_image).save(image_path)

    result = assessor.assess(image_path)

    assert result["overall_status"] in ["POOR", "UNGRADABLE"]
    assert result["is_acceptable"] is False
    assert "checks" in result
    assert "brightness" in result["checks"]


def test_assess_image_quality_good_image(tmp_path):
    assessor = get_quality_assessor()

    # Create an image with sufficient resolution, brightness, and contrast
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.circle(img, (200, 200), 100, (120, 180, 220), -1)
    cv2.rectangle(img, (50, 50), (150, 150), (200, 100, 80), -1)
    cv2.line(img, (0, 0), (400, 400), (255, 255, 255), 3)
    img = np.clip(img.astype(np.int32) + 60, 0, 255).astype(np.uint8)

    image_path = str(tmp_path / "good.jpg")
    Image.fromarray(img).save(image_path)

    result = assessor.assess(image_path)
    assert result["overall_status"] == "ACCEPTABLE"
    assert result["is_acceptable"] is True
    assert result["overall_score"] >= 0.7


def test_assess_nonexistent_image():
    assessor = get_quality_assessor()
    result = assessor.assess("nonexistent_path_12345.jpg")
    assert result["overall_status"] == "UNGRADABLE"
    assert result["is_acceptable"] is False

