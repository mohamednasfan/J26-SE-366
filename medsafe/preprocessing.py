"""Document preprocessing shared across all OCR engines.

Preprocessing changes only the OCR input image. Original user uploads remain
untouched and retained for review. Quality scores are image heuristics, never
confidence in medicine identity or clinical safety.
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageOps

MODES = ("none", "clahe", "adaptive", "deskew_clahe")


def _dependencies():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OpenCV preprocessing requires opencv-python-headless and numpy") from exc
    return cv2, np


def image_quality(image: Image.Image) -> dict:
    """Return reproducible, *uncalibrated* contrast and blur diagnostics."""
    cv2, np = _dependencies()
    gray = np.asarray(ImageOps.grayscale(image))
    if gray.size == 0:
        raise ValueError("Empty image")
    contrast = float(np.percentile(gray, 95) - np.percentile(gray, 5))
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    warnings = []
    if contrast < 50:
        warnings.append("LOW_CONTRAST_IMAGE")
    if blur_variance < 35:
        warnings.append("POSSIBLY_BLURRED_IMAGE")
    if min(image.size) < 380:
        warnings.append("LOW_SOURCE_RESOLUTION")
    return {
        "contrast_p95_p05": round(contrast, 2),
        "laplacian_variance": round(blur_variance, 2),
        "warnings": warnings,
        "scores_clinically_calibrated": False,
    }


def _estimate_skew(gray, cv2, np):
    """Find dominant near-horizontal strokes without assuming a page template."""
    edges = cv2.Canny(gray, 65, 160)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=70,
        minLineLength=max(50, gray.shape[1] // 7),
        maxLineGap=18,
    )
    if lines is None:
        return 0.0
    angles = []
    for (x1, y1, x2, y2) in lines[:, 0]:
        if x2 == x1:
            continue
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if abs(angle) <= 12:
            angles.append(angle)
    if len(angles) < 3:
        return 0.0
    angle = float(np.median(angles))
    return angle if abs(angle) >= .35 else 0.0


def enhance_image(image: Image.Image, mode: str = "none"):
    """Return (enhanced PIL RGB, metadata). No source-image mutation."""
    if mode not in MODES:
        raise ValueError("Unknown preprocessing mode")
    rgb = image.convert("RGB")
    if rgb.width * rgb.height > 15_000_000:
        raise ValueError("Image pixel count exceeds limit")
    if mode == "none":
        return rgb.copy(), {
            "mode": mode, "deskew_degrees": 0.0,
            "quality": None, "clinical_confidence": None,
        }
    cv2, np = _dependencies()
    gray = np.asarray(ImageOps.grayscale(rgb))
    measured = image_quality(rgb)
    angle = 0.0
    if mode == "deskew_clahe":
        angle = _estimate_skew(gray, cv2, np)
        if angle:
            h, w = gray.shape
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            gray = cv2.warpAffine(
                gray, matrix, (w, h), flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT, borderValue=255,
            )
    if mode in ("clahe", "deskew_clahe"):
        filtered = cv2.bilateralFilter(gray, 5, 36, 36)
        transformed = cv2.createCLAHE(
            clipLimit=2.0, tileGridSize=(8, 8)
        ).apply(filtered)
    else:
        transformed = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 35, 11,
        )
    result = Image.fromarray(transformed).convert("RGB")
    return result, {
        "mode": mode,
        "deskew_degrees": round(angle, 2),
        "quality": measured,
        "clinical_confidence": None,
    }


def prepare_ocr_bytes(data: bytes, mode: str = "none"):
    """Return PNG OCR input and its provenance, not the original stored image."""
    from .ocr import decode_image

    if mode == "none":
        return data, {
            "mode": mode, "deskew_degrees": 0.0,
            "quality": None, "clinical_confidence": None,
        }
    image = decode_image(data)
    enhanced, metadata = enhance_image(image, mode=mode)
    stream = BytesIO()
    enhanced.save(stream, format="PNG", optimize=False)
    return stream.getvalue(), metadata
