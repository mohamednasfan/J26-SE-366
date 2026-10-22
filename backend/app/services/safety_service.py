"""Medication safety service facade; all checks remain evidence-gated."""
from medsafe.pipeline import analyze_text

__all__ = ["analyze_text"]
