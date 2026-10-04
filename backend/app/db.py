import os, sqlite3
from pathlib import Path

def db_path() -> Path:
    d = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d / "wishclaim.db"

def connect(immediate: bool = False):
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    if immediate:
        # Serialize read-check-then-write paths (e.g. claim mutex).
        c.isolation_level = None
        c.execute("BEGIN IMMEDIATE")
    return c
