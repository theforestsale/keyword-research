import io
import json
import pytest
from app import create_app
from config import TestConfig
from models import db, Search, Keyword, Folder
from services.ai_researcher import (
    expand_keywords,
    classify_intent,
    cluster_content,
    ppc_forecast,
    AIResearchError,
)


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_search(app):
    with app.app_context():
        s = Search(seed_keyword="coffee")
        db.session.add(s)
        db.session.flush()
        for i in range(3):
            db.session.add(Keyword(
                search_id=s.id, keyword=f"coffee bean {i}",
                volume_est=100 * i + 10, difficulty_est=20 + i,
                intent="commercial", cpc_est=1.5,
            ))
        db.session.commit()
        sid = s.id
    return sid


def test_folder_create_and_delete(client):
    resp = client.post("/folders/create", data={"name": "My Group"})
    assert resp.status_code == 302
    with client.application.app_context():
        f = Folder.query.filter_by(name="My Group").first()
        assert f is not None
        fid = f.id
    resp = client.post(f"/folders/{fid}/delete")
    assert resp.status_code == 302
    with client.application.app_context():
        assert db.session.get(Folder, fid) is None


def test_folder_create_empty(client):
    resp = client.post("/folders/create", data={"name": ""})
    assert resp.status_code == 302


def test_search_rename(client, sample_search):
    resp = client.post(f"/search/{sample_search}/rename", data={"name": "new name"})
    assert resp.status_code == 302
    with client.application.app_context():
        assert db.session.get(Search, sample_search).seed_keyword == "new name"


def test_search_assign_folder(client, sample_search):
    with client.application.app_context():
        f = Folder(name="F")
        db.session.add(f)
        db.session.commit()
        fid = f.id
    resp = client.post(f"/search/{sample_search}/assign", data={"folder_id": str(fid)})
    assert resp.status_code == 302
    with client.application.app_context():
        assert db.session.get(Search, sample_search).folder_id == fid


def test_search_delete(client, sample_search):
    resp = client.post(f"/search/{sample_search}/delete")
    assert resp.status_code == 302
    with client.application.app_context():
        assert db.session.get(Search, sample_search) is None
        assert Keyword.query.filter_by(search_id=sample_search).count() == 0


def test_compare_page(client, sample_search):
    resp = client.get("/compare")
    assert resp.status_code == 200
    assert b"Compare" in resp.data


def test_import_page_get(client):
    resp = client.get("/import")
    assert resp.status_code == 200


def test_import_rejects_non_csv(client):
    resp = client.post("/import", data={"file": (io.BytesIO(b"not a csv"), "x.txt")},
                       content_type="multipart/form-data")
    assert resp.status_code == 302


def test_import_parses_no_rows(client):
    data = {"file": (io.BytesIO(b"header\nacoffee\n"), "x.csv")}
    resp = client.post("/import", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200


# ----- AI service advanced functions (mocked client) -----

class FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeCompletion(self.reply)


def test_expand_keywords():
    client = FakeClient('{"terms": ["a", "b"]}')
    out = expand_keywords(client, "m", "coffee", 10)
    assert out == ["a", "b"]


def test_classify_intent():
    client = FakeClient('{"results": [{"keyword": "coffee", "intent": "informational"}]}')
    out = classify_intent(client, "m", ["coffee"])
    assert out.get("coffee") == "informational"


def test_cluster_content():
    client = FakeClient('{"clusters": [{"title": "T", "keywords": ["k1"], "brief": "b"}]}')
    out = cluster_content(client, "m", ["k1"], "coffee")
    assert out[0]["title"] == "T"
    assert out[0]["keywords"] == ["k1"]


def test_ppc_forecast():
    client = FakeClient('{"estimates": [{"keyword": "coffee", "impressions": 1000, "ctr": 0.03, "clicks": 30, "cpc": 1.2, "monthly_cost": 36}]}')
    out = ppc_forecast(client, "m", ["coffee"])
    assert out[0]["cpc"] == 1.2
    assert out[0]["monthly_cost"] == 36
