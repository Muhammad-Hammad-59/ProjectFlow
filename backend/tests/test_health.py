from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db.session import get_engine
from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unreachable_database():
    dead = create_engine("postgresql+psycopg://nobody:x@127.0.0.1:1/none?connect_timeout=2")
    app.dependency_overrides[get_engine] = lambda: dead
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}
