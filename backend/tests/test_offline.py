"""Offline tests (no API key needed):  pytest -q"""
import os
import sys
from pathlib import Path

os.environ["MOCK_AI"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import ai  # noqa: E402
from main import app  # noqa: E402
from risk import score_cod_order  # noqa: E402

client = TestClient(app)


def test_extract_json_handles_thinking_and_fences():
    raw = '<think>hmm</think>```json\n{"language":"english","intent":"faq","urgent":false}\n```'
    assert ai.extract_json(raw)["intent"] == "faq"


def test_clean_rejects_bad_values():
    assert ai._clean({"language": "french", "intent": "dance"}) == {
        "language": "roman_urdu", "intent": "other", "urgent": False}


def test_chat_endpoint():
    r = client.post("/chat", json={"phone": "03001234567", "message": "Delivery charges kitne hain?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] and body["language"] == "roman_urdu" and body["intent"] == "faq"


def test_takeover_pauses_ai():
    client.post("/conversations/03009999999/takeover", params={"paused": True})
    r = client.post("/chat", json={"phone": "03009999999", "message": "hello"})
    assert r.json()["ai_paused"] is True and r.json()["reply"] == ""


def test_risk_vague_address_new_big_order_is_high():
    r = score_cod_order("Gulshan", total=9500)
    assert r["level"] == "high"


def test_risk_good_repeat_customer_is_low():
    r = score_cod_order("House 12, Street 5, Block 13-D, near Masjid Baitul Mukarram, Gulshan",
                        total=2200, completed_orders=4)
    assert r["level"] == "low"


def test_risk_past_cancellations_capped():
    r = score_cod_order("House 12, Street 5, near park", total=1000, past_cancellations=5)
    assert r["points"] == 4 and r["level"] == "high"
