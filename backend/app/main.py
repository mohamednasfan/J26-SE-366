"""Stable backend entry point; domain services remain in the legacy-compatible package."""
from medsafe.api_product import app

__all__ = ["app"]
