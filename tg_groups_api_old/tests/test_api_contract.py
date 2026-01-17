from fastapi.testclient import TestClient

import app
import tg_service

client = TestClient(app.app)


def test_search_groups_contract(monkeypatch):
    async def fake_search_groups(*args, **kwargs):
        return [
            {
                "id": 1,
                "title": "t",
                "username": "u",
                "members_count": 10,
                "type": "group",
                "status": "ok",
                "reason": None,
            }
        ]

    # patch both possible call-sites
    monkeypatch.setattr(app, "search_groups", fake_search_groups, raising=False)
    monkeypatch.setattr(tg_service, "search_groups", fake_search_groups, raising=False)

    r = client.post("/search_groups", json={"query": "x"})
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, dict)
    assert data.get("ok") is True
    assert data.get("query") == "x"
    assert isinstance(data.get("items"), list)
    assert len(data["items"]) >= 1
    assert "status" in data["items"][0]
    assert "reason" in data["items"][0]
