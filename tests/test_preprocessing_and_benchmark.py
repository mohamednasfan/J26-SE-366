"""Non-destructive image enhancements and complete OCR research contracts."""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from PIL import Image, ImageDraw

from medsafe.preprocessing import MODES, enhance_image, image_quality, prepare_ocr_bytes
from backend.app.research.benchmark import (
    read_manifest, run_benchmark, _synthetic_screen,
)


def source_image():
    im = Image.new("RGB", (650, 280), "#f6f4ed")
    draw = ImageDraw.Draw(im)
    draw.text((20, 60), "Medicine: SYNTHMED-01", fill="black")
    draw.text((20, 110), "Dose: 125 mg", fill="black")
    draw.text((20, 160), "Frequency: twice daily", fill="black")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("mode", MODES)
def test_each_preprocessing_mode_preserves_dimensions_and_input(mode):
    data = source_image()
    before = hashlib.sha256(data).hexdigest()
    enhanced, details = prepare_ocr_bytes(data, mode)
    assert hashlib.sha256(data).hexdigest() == before
    assert Image.open(io.BytesIO(enhanced)).size == (650, 280)
    assert details["mode"] == mode
    assert details["clinical_confidence"] is None
    if mode != "none":
        assert details["quality"]["scores_clinically_calibrated"] is False


def test_invalid_preprocessing_mode():
    with pytest.raises(ValueError, match="Unknown preprocessing"):
        enhance_image(Image.new("RGB", (300, 150)), mode="untrusted")


def test_low_contrast_quality_is_diagnostic_not_clinical():
    assert "LOW_CONTRAST_IMAGE" in image_quality(
        Image.new("RGB", (650, 280), (235, 235, 235))
    )["warnings"]


def test_ocr_upload_keeps_original_bytes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import medsafe.storage as storage
    import medsafe.api_product as product

    monkeypatch.setattr(storage, "DATA", tmp_path)
    monkeypatch.setattr(product, "recognize", lambda data, engine: {
        "text": "Medicine: SYNTHMED-01\nDose: 125 mg",
        "engine": engine, "warnings": ["RESEARCH_ONLY"], "confidence": None,
        "regions": [], "boxes": [],
    })
    raw = source_image()
    with TestClient(product.app) as client:
        response = client.post(
            "/api/prescriptions?engine=tesseract&preprocess=clahe",
            files={"file": ("synthetic.png", raw, "image/png")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ocr"]["preprocessing"]["mode"] == "clahe"
        assert body["ocr"]["processing_seconds"] >= 0
        assert client.get(f"/api/prescriptions/{body['id']}/image").content == raw
        assert body["clinical_clearance"] is False
        assert body["can_auto_dispense"] is False


def test_human_manifest_needs_only_ground_truth_not_predictions(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "sample.png").write_bytes(source_image())
    item = {
        "image_id": "human-01", "image_path": "sample.png",
        "gold_transcript": "Medicine: SYNTHMED-01\nDose: 125 mg",
        "gold": {"medicine": "SYNTHMED-01", "dose": "125 mg"},
        "split": "test", "human_verified": True, "reviewer_id": "human-annotator",
        "gold_alert": True, "gold_age_flag": False,
    }
    path = dataset / "manifest.jsonl"
    path.write_text(json.dumps(item) + "\n")
    assert read_manifest(path)[0]["image_id"] == "human-01"


def test_end_to_end_evaluation_requires_covered_alerts(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "sample.png").write_bytes(source_image())
    item = {
        "image_id": "human-01", "image_path": "sample.png",
        "gold_transcript": "Medicine: SYNTHMED-01\nDose: 125 mg",
        "gold": {"medicine": "SYNTHMED-01", "dose": "125 mg"},
        "split": "test", "human_verified": True, "reviewer_id": "annotator",
        "gold_alert": True, "gold_age_flag": False,
    }
    path = dataset / "manifest.jsonl"
    path.write_text(json.dumps(item) + "\n")
    monkeypatch.setattr("backend.app.research.benchmark.recognize", lambda data, engine: {
        "text": "Medicine: SYNTHMED-01\nDose: 125 mg",
        "warnings": ["STUB_TEST_ONLY"],
    })
    monkeypatch.setattr("backend.app.research.benchmark._reviewed_screen", lambda text: (None, None))
    result = run_benchmark(path, engines=["tesseract"])
    tested = result["engines"]["tesseract"]
    assert tested["ocr_eligible"] is True
    assert tested["dose_alert_evaluated_n"] == 0
    assert tested["age_alert_evaluated_n"] == 0
    assert tested["thesis_eligible"] is False


def test_synthetic_alerts_have_fictional_thresholds_only():
    rule = {
        "max_single_mg": 100, "max_daily_mg": 200,
        "min_age_years": 12, "max_age_years": 65,
    }
    fields = {
        "medicine": "SYNTHMED-03", "dose": "125 mg",
        "frequency": "twice daily", "age": "9 years",
    }
    assert _synthetic_screen(fields, rule) == (True, True)
    assert _synthetic_screen({**fields, "medicine": "unidentified"}, rule) == (None, None)
