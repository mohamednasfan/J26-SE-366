"""Local SQLite persistence boundary."""
from medsafe.storage import connect, create, delete, get, rows, update

__all__ = ["connect", "create", "delete", "get", "rows", "update"]
