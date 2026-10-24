"""Tests for the market price check (Tavily + Nemotron Super + Python maths). No keys needed."""
import os
import sys
from pathlib import Path

os.environ["MOCK_AI"] = "1"
os.environ["FIREBASE_CREDENTIALS"] = ""
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import ai  # noqa: E402
import db  # noqa: E402
import market  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    db.store.data.clear()
    db.load_sample_shop(force=True)
    monkeypatch.setattr(market, "TAVILY_READY", False)


def test_compare_is_pure_maths():
    prices = [{"price": p} for p in (2000, 2200, 2400, 50, 99999)]  # 50 and 99999 are thrown away
    r = market.compare(2200, prices)
    assert r["found"] == 3 and r["typical"] == 2200 and r["low"] == 2000 and r["high"] == 2400
    assert r["verdict"] == "similar"
    assert market.compare(3000, prices)["verdict"] == "higher"
    assert market.compare(1500, prices)["verdict"] == "lower"
    assert market.compare(2200, [{"price": 2100}])["verdict"] == "not_enough_data"


def test_regex_reads_rupee_prices():
    res = [{"title": "A", "content": "Cake Rs 2,450 and PKR 2600, delivery free"}]
    assert [p["price"] for p in market.regex_prices(res)] == [2450, 2600]


def test_check_without_keys_uses_labelled_sample_and_caches():
    r = client.post("/market/check", json={"product_id": "p1"}).json()
    assert r["search"].startswith("sample") and r["model_used"] == "pattern"
    assert r["verdict"] in ("similar", "higher", "lower") and r["found"] >= 2
    assert all("example.com" in s["url"] for s in r["sources"])
    again = client.post("/market/check", json={"product_id": "p1"}).json()
    assert again["cached"] is True
    assert client.get("/market/checks").json()[0]["product_id"] == "p1"


def test_unknown_product_is_400():
    assert client.post("/market/check", json={"product_id": "nope"}).status_code == 400


def test_tavily_call_shape_and_daily_limit(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return httpx.Response(200, json={"results": [
            {"title": "X Bakers", "url": "https://x.pk", "content": "Chocolate Fudge Cake 2kg Rs 4,200"},
            {"title": "Y Cakes", "url": "https://y.pk", "content": "2kg chocolate cake PKR 4,800"}]},
            request=httpx.Request("POST", url))

    monkeypatch.setattr(market, "TAVILY_READY", True)
    monkeypatch.setattr(market, "TAVILY_KEY", "tvly-test")
    monkeypatch.setattr(market.httpx, "post", fake_post)
    r = client.post("/market/check", json={"product_id": "p1"}).json()
    assert sent["url"] == "https://api.tavily.com/search"
    assert sent["headers"]["Authorization"] == "Bearer tvly-test"
    assert sent["body"]["search_depth"] == "basic" and sent["body"]["country"] == "pakistan"
    assert r["search"] == "tavily" and r["typical"] == 4500
    assert db.get_usage()["tavily_calls"] == 1

    monkeypatch.setattr(market, "TAVILY_DAILY_LIMIT", 1)
    blocked = client.post("/market/check", json={"product_id": "p1", "refresh": True})
    assert blocked.status_code == 429


def test_tavily_error_is_friendly(monkeypatch):
    def broken(*a, **k):
        raise httpx.ConnectError("no internet")

    monkeypatch.setattr(market, "TAVILY_READY", True)
    monkeypatch.setattr(market.httpx, "post", broken)
    r = client.post("/market/check", json={"product_id": "p1"})
    assert r.status_code == 502 and "Web search failed" in r.json()["detail"]


def test_super_reads_prices_when_live(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat", lambda *a, **k: '{"prices": [{"price": "4,100", "source": 0, "what": "x"},'
                                                    ' {"price": 4300, "source": 1}], "note": "Most shops charge about Rs 4,200."}')
    prices, note, model = market.read_prices("Cake", [{"title": "a", "url": "u", "content": "c"}] * 2, "english")
    assert [p["price"] for p in prices] == [4100, 4300] and model == ai.SUPER and "4,200" in note


def test_advice_gets_real_market_prices_only(monkeypatch):
    client.post("/admin/load-demo", params={"days": 30})
    client.post("/market/check", json={"product_id": "p1"})  # sample data -> flagged as sample
    checks = market.for_advice()
    assert checks and checks[0]["sample_data"] is True


def test_health_and_usage_show_tavily():
    h = client.get("/").json()
    assert "tavily" in h and "whatsapp" in h
    u = client.get("/usage").json()
    assert "tavily_searches" in u and u["limits"]["tavily_per_day"] >= 1 and "nano" in u["by_model"]


def test_daily_report_job_saves_and_formats():
    client.post("/admin/load-demo", params={"days": 7})
    r = client.post("/admin/run-daily-report").json()
    assert "report for" in r["text"] and "Sales: Rs" in r["text"] and r["sent_to_whatsapp"] is False
    assert client.get("/reports").json()[0]["date"] == r["date"]


def test_regex_skips_delivery_and_minimum_amounts():
    res = [{"title": "A", "content": "Cake Rs 2,450. Free delivery above Rs 3,000, save Rs 200"}]
    assert [p["price"] for p in market.regex_prices(res)] == [2450]
