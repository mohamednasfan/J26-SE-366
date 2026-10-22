"""Baseline OCR token-level evidence is visible but cannot auto-validate clinical fields."""
from io import BytesIO
from PIL import Image
from medsafe import ocr_product

def _image():
    output=BytesIO()
    Image.new("RGB",(180,80),"white").save(output,format="PNG")
    return output.getvalue()

def test_tesseract_tokens_are_reviewable_but_never_clinically_calibrated(monkeypatch):
    monkeypatch.setattr(ocr_product,"_tesseract",lambda im:{
        "text":"Medicine: FictionalTest",
        "token_regions":[{"id":1,"text":"FictionalTest",
                          "box":[10,12,90,32],"confidence":.52,
                          "confidence_is_calibrated":False,"verified":False}],
        "confidence":.52,
    })
    result=ocr_product.recognize(_image(),engine="tesseract")
    assert result["regions"][0]["confidence"]==.52
    assert result["regions"][0]["verified"] is False
    assert result["regions"][0]["confidence_is_calibrated"] is False
    assert result["boxes"]==[[10,12,90,32]]
    assert result["confidence"] is None
    assert "TOKEN_CONFIDENCE_NOT_CLINICALLY_CALIBRATED" in result["warnings"]
