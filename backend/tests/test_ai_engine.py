import sys
import os
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest
from PIL import Image

from services.ai_engine import AIEngine, get_ai_engine
from services.explainability import ExplainabilityService, get_explainability_service
from services.recommendation import get_recommendation


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a temporary valid RGB test image using PIL."""
    img_path = str(tmp_path / "sample_retina.jpg")
    img = np.full((300, 300, 3), 128, dtype=np.uint8)
    cv2.circle(img, (150, 150), 60, (50, 100, 200), -1)
    Image.fromarray(img).save(img_path)
    return img_path


def test_ai_engine_demo_mode(sample_image_path):
    """Verify demo mode behavior when no trained weights exist."""
    engine = AIEngine()

    with patch("services.ai_engine.get_model", return_value=(None, False)):
        result = engine.analyze(sample_image_path)

        assert result["is_demo"] is True
        assert result["status"] == "demo"
        assert result["classification"] == "DEMO — No Real Model Loaded"
        assert result["confidence"] is None
        assert result["predicted_class_index"] is None
        assert "⚠️ DEMO MODE" in result["screening_limitations"]
        assert result["classification"] != "Normal"

        # Fixed zero probabilities in demo mode — no fabricated confidences
        for label, prob in result["probabilities"].items():
            assert prob == 0.0


def test_ai_engine_real_inference_mocked(sample_image_path):
    """Verify real model inference parsing with a mocked model."""
    mock_torch = MagicMock()
    mock_torch.FloatTensor = MagicMock()
    mock_model = MagicMock()
    mock_outputs = MagicMock()
    mock_model.return_value = mock_outputs

    mock_probs_tensor = MagicMock()
    mock_probs_tensor.squeeze.return_value.numpy.return_value = np.array([0.05, 0.90, 0.05])
    mock_torch.nn.functional.softmax.return_value = mock_probs_tensor

    # Mock no_grad context manager
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock()
    mock_ctx.__exit__ = MagicMock()
    mock_torch.no_grad.return_value = mock_ctx

    engine = AIEngine()

    with patch.dict(sys.modules, {"torch": mock_torch}):
        with patch("services.ai_engine.get_model", return_value=(mock_model, True)):
            result = engine.analyze(sample_image_path)

            assert result["is_demo"] is False
            assert result["status"] == "completed"
            assert result["predicted_class_index"] == 1
            assert result["classification"] == "Pre-Plus/Mild"
            assert result["confidence"] == 0.9
            assert isinstance(result["probabilities"], dict)
            assert len(result["probabilities"]) == 3
            assert "Normal" in result["probabilities"]


def test_ai_engine_inference_failure_safety(sample_image_path):
    """Verify that model failure never returns a false 'Normal' result."""
    engine = AIEngine()

    # Mock a model whose forward pass throws a runtime error
    mock_failing_model = MagicMock(side_effect=RuntimeError("CUDA out of memory or corrupted tensor"))

    with patch("services.ai_engine.get_model", return_value=(mock_failing_model, True)):
        result = engine.analyze(sample_image_path)

        assert result["is_demo"] is False
        assert result["status"] == "failed"
        assert result["classification"] is None
        assert result["confidence"] is None
        assert result["classification"] != "Normal"
        assert "error" in result
        assert "Manual specialist review is required" in result["screening_limitations"]


def test_explainability_demo_generation(sample_image_path, tmp_path):
    """Verify explainability heatmap generation in demo mode."""
    service = ExplainabilityService()
    session_id = "TEST-SESSION-001"
    image_id = "IMG-001"

    with patch("services.explainability.get_model", return_value=(None, False)):
        result = service.generate(sample_image_path, session_id, image_id)

        assert result["is_demo"] is True
        assert result["status"] == "demo"
        assert result["heatmap_url"] is not None
        assert result["overlay_url"] is not None
        assert "DEMO VISUALIZATION" in result["explanation"]


def test_recommendations_safety_for_abnormal_or_failed():
    """Verify protocol recommendations never report routine for abnormal, failed, or demo states."""
    rec_demo = get_recommendation("DEMO — No Real Model Loaded", "demo")
    assert rec_demo["urgency"] == "demo"
    assert "DEMO MODE" in rec_demo["recommendation"]

    rec_failed = get_recommendation(None, "failed")
    assert rec_failed["urgency"] == "review"
    assert "technical error" in rec_failed["recommendation"]

    rec_ungradable = get_recommendation("Ungradable", "ungradable")
    assert rec_ungradable["urgency"] == "review"
    assert "could not be assessed" in rec_ungradable["recommendation"]

