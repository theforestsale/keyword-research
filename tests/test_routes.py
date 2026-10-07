import pytest
from app import create_app
from config import TestConfig


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AI Keyword Research" in resp.data


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_research_redirects_without_api_key(app, client, monkeypatch):
    monkeypatch.setattr("config.Config.AI_API_KEY", "")
    resp = client.post("/research", data={"seed": "coffee", "count": "5"})
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_research_empty_seed_rejected(client, monkeypatch):
    monkeypatch.setattr("config.Config.AI_API_KEY", "fake-key")
    resp = client.post("/research", data={"seed": "", "count": "5"})
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_research_long_seed_rejected(app, client, monkeypatch):
    monkeypatch.setattr("config.Config.AI_API_KEY", "fake-key")
    monkeypatch.setattr("config.Config.MAX_SEED_LENGTH", 10)
    resp = client.post("/research", data={"seed": "way too long keyword here", "count": "5"})
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_export_empty_results(client, app):
    from models import Search
    with app.app_context():
        s = Search(seed_keyword="test")
        from models import db
        db.session.add(s)
        db.session.commit()
        sid = s.id
    resp = client.get(f"/results/{sid}/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    assert "Keyword,Volume" in resp.data.decode()


def test_view_missing_results_404(client):
    resp = client.get("/results/99999")
    assert resp.status_code == 404
