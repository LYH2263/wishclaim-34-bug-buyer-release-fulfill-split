import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the sqlite file at an isolated temp dir before app code connects.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import seed
    seed.init_db()
    from app.main import app
    with TestClient(app) as c:
        yield c
