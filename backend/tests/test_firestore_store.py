"""Runs the main flows through the real FirestoreStore class, with a small in-memory stand-in for
Google's Firestore client (same method names: collection, document, get, set(merge), stream, Increment).
The real database is not touched; this checks our code calls Firestore the right way."""
import os
import sys
from pathlib import Path

os.environ["MOCK_AI"] = "1"
os.environ["FIREBASE_CREDENTIALS"] = ""
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402
from firebase_admin import firestore  # noqa: E402

import db  # noqa: E402


class _Snap:
    def __init__(self, col, doc_id):
        self._col, self.id = col, doc_id
        self.exists = doc_id in col.docs
        self.reference = _Doc(col, doc_id)

    def to_dict(self):
        return dict(self._col.docs[self.id]) if self.exists else None


class _Doc:
    def __init__(self, col, doc_id):
        self.col, self.id = col, doc_id

    def get(self):
        return _Snap(self.col, self.id)

    def set(self, data, merge=False):
        base = dict(self.col.docs.get(self.id, {})) if merge else {}
        for k, v in data.items():
            if isinstance(v, firestore.Increment):
                base[k] = base.get(k, 0) + v.value
            else:
                base[k] = v
        self.col.docs[self.id] = base

    def delete(self):
        self.col.docs.pop(self.id, None)


class _Col:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        return _Doc(self, doc_id)

    def stream(self):
        return [_Snap(self, k) for k in list(self.docs)]


class FakeFirestore:
    def __init__(self):
        self.cols = {}

    def collection(self, name):
        return self.cols.setdefault(name, _Col())


@pytest.fixture()
def fs(monkeypatch):
    store = db.FirestoreStore.__new__(db.FirestoreStore)  # skip real login
    store.fs = FakeFirestore()
    monkeypatch.setattr(db, "store", store)
    return store


def test_catalog_and_customer_flow(fs):
    import tools
    db.load_sample_shop(force=True)
    assert len(db.get_products()) == 8 and db.get_shop()["name"] == "Sweet Crumbs Bakery"
    phone = "03190000000"
    db.add_message(phone, "customer", "Haan confirm")
    tools.check_discount(phone, "p1")
    from datetime import timedelta
    when = f"{(db.now_karachi() + timedelta(days=2)).date().isoformat()} 18:00"
    assert tools.preview_order(phone, [{"product_id": "p1", "quantity": 1}], "Ali",
                               "House 1, Street 2, near park, DHA", when)["ok"]
    r = tools.confirm_order(phone)
    assert r["ok"] and db.get_order(r["order_id"])["total"] == round(2200 * 0.95) + 200
    assert tools.get_customer(phone)["name"] == "Ali"


def test_usage_increment_and_lists(fs):
    db.add_usage({"messages": 1, "cost_usd": 0.5})
    db.add_usage({"messages": 2, "cost_usd": 0.25})
    assert db.get_usage()["messages"] == 3 and db.get_usage()["cost_usd"] == 0.75
    fid = db.add_flag("complaint", "0300", "late")
    assert db.list_flags()[0]["id"] == fid
    db.resolve_flag(fid)
    assert db.list_flags() == []


def test_chat_endpoint_on_firestore(fs):
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.post("/chat", json={"phone": "03191111111", "message": "Delivery kitne ki hai?"})
    assert r.status_code == 200 and r.json()["reply"]
    assert c.get("/conversations").json()[0]["phone"] == "03191111111"
    assert c.get("/usage").json()["messages"] == 1
