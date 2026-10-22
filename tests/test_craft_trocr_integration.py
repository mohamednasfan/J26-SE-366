"""CRAFT + Notebook44 TrOCR integration: no silent fallback or lost reading order."""
from io import BytesIO

import pytest
from PIL import Image

from medsafe import ocr_product


def _image():
    out=BytesIO()
    Image.new("RGB",(320,200),"white").save(out,format="PNG")
    return out.getvalue()


def test_missing_checkpoint_blocks_craft_trocr_even_when_no_text(monkeypatch):
    monkeypatch.setattr(ocr_product,"checkpoint_status",lambda:{"ready_for_load":False})
    monkeypatch.setattr(ocr_product,"_boxes",lambda image:[])
    with pytest.raises(ocr_product.OCRUnavailable,match="checkpoint"):
        ocr_product.recognize(_image(),"craft_trocr")


def test_empty_craft_detection_requires_manual_transcription(monkeypatch):
    monkeypatch.setattr(ocr_product,"checkpoint_status",lambda:{"ready_for_load":True})
    monkeypatch.setattr(ocr_product,"_boxes",lambda image:[])
    result=ocr_product.recognize(_image(),"craft_trocr")
    assert result["text"]==""
    assert "MANUAL_TRANSCRIPTION_REQUIRED" in result["warnings"]
    assert result["confidence"] is None


def test_craft_trocr_returns_regions_in_transcription_order(monkeypatch):
    # Detector order is intentionally scrambled: right-bottom, left-top, right-top.
    boxes=[(150,130,250,155),(10,20,100,45),(150,20,270,45)]
    monkeypatch.setattr(ocr_product,"checkpoint_status",lambda:{"ready_for_load":True})
    monkeypatch.setattr(ocr_product,"_boxes",lambda image:boxes)
    monkeypatch.setattr(ocr_product,"_trocr_lines",lambda image,boxes:["third","first","second"])
    result=ocr_product.recognize(_image(),"craft_trocr")
    assert result["text"]=="first second\nthird"
    assert [r["text"] for r in result["regions"]]==["first","second","third"]
    assert [r["reading_order"] for r in result["regions"]]==[1,2,3]
    assert result["boxes"]==[r["box"] for r in result["regions"]]
    assert result["confidence"] is None
    assert all(r["verified"] is False for r in result["regions"])


def test_craft_trocr_rejects_partial_recognition(monkeypatch):
    monkeypatch.setattr(ocr_product,"checkpoint_status",lambda:{"ready_for_load":True})
    monkeypatch.setattr(ocr_product,"_boxes",lambda image:[(10,20,100,45)])
    monkeypatch.setattr(ocr_product,"_trocr_lines",lambda image,boxes:[])
    with pytest.raises(ocr_product.OCRUnavailable,match="count mismatch"):
        ocr_product.recognize(_image(),"craft_trocr")
