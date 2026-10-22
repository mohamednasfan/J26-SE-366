"""OCR service facade used by API integrations and smoke tests."""
from medsafe.ocr_product import OCRUnavailable, recognize, status

__all__ = ["OCRUnavailable", "recognize", "status"]
