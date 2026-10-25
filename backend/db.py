"""Database helpers.

If FIREBASE_CREDENTIALS points to a Firebase service-account JSON file, data is stored in
Firestore. If it is empty, everything is kept in memory (lost on restart) - fine for tests.
The rest of the code only calls the functions at the bottom, never Firestore directly.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SAMPLE = Path(__file__).parent.parent / "sample_data" / "shop.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_karachi() -> datetime:
    """Shop's local time (all shop hours and 'today' limits use this)."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return datetime.now(ZoneInfo(os.getenv("SHOP_TIMEZONE", "Asia/Karachi")))
    except ZoneInfoNotFoundError:  # no time-zone data installed (e.g. Windows without tzdata)
        return datetime.now(timezone(timedelta(hours=5), "PKT"))  # Pakistan: UTC+5, no daylight saving


def today_key() -> str:
    return now_karachi().date().isoformat()


def local_date(iso_time: str) -> str:
    """'YYYY-MM-DD' of a saved UTC time, in the shop's time zone (so a 1 am order counts for that day)."""
    try:
        return datetime.fromisoformat(iso_time).astimezone(now_karachi().tzinfo).date().isoformat()
    except (ValueError, TypeError):
        return (iso_time or "")[:10]


# ------------------------------------------------------------------ two storage engines
class MemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}

    def get(self, col, doc_id):
        d = self.data.get(col, {}).get(doc_id)
        return dict(d) if d else None

    def set(self, col, doc_id, value):
        self.data.setdefault(col, {})[doc_id] = dict(value)

    def update(self, col, doc_id, fields):
        self.data.setdefault(col, {}).setdefault(doc_id, {}).update(fields)

    def all(self, col):
        return [dict(v, id=k) for k, v in self.data.get(col, {}).items()]

    def delete_all(self, col):
        self.data.pop(col, None)

    def incr(self, col, doc_id, amounts):
        doc = self.data.setdefault(col, {}).setdefault(doc_id, {})
        for k, v in amounts.items():
            doc[k] = doc.get(k, 0) + v


class FirestoreStore:
    def __init__(self, cred_path):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            # cred_path is a file path, or (on Vercel) the whole JSON text of the key
            key = json.loads(cred_path) if cred_path.startswith("{") else cred_path
            firebase_admin.initialize_app(credentials.Certificate(key))
        self.fs = firestore.client()

    def get(self, col, doc_id):
        snap = self.fs.collection(col).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def set(self, col, doc_id, value):
        self.fs.collection(col).document(doc_id).set(value)

    def update(self, col, doc_id, fields):
        self.fs.collection(col).document(doc_id).set(fields, merge=True)

    def all(self, col):
        return [dict(s.to_dict(), id=s.id) for s in self.fs.collection(col).stream()]

    def delete_all(self, col):
        for s in self.fs.collection(col).stream():
            s.reference.delete()

    def incr(self, col, doc_id, amounts):
        from firebase_admin import firestore

        self.fs.collection(col).document(doc_id).set(
            {k: firestore.Increment(v) for k, v in amounts.items()}, merge=True)


_cred = os.getenv("FIREBASE_CREDENTIALS", "").strip()
store = FirestoreStore(_cred) if _cred else MemoryStore()
USING_FIRESTORE = bool(_cred)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ------------------------------------------------------------------ shop, products, FAQs
def load_sample_shop(force: bool = False) -> None:
    """Put the demo shop into the database if it is empty (or always, with force=True)."""
    if store.get("shop", "main") and not force:
        return
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    save_catalog(data["shop"], data["products"], data["faqs"])


def save_catalog(shop: dict, products: list[dict], faqs: list[dict]) -> None:
    store.set("shop", "main", shop)
    store.delete_all("products")
    for i, p in enumerate(products):
        pid = p.get("id") or f"p{i + 1}"
        store.set("products", pid, {k: v for k, v in p.items() if k != "id"})
    store.delete_all("faqs")
    for i, f in enumerate(faqs):
        store.set("faqs", f"f{i + 1}", {"question": f["question"], "answer": f["answer"]})


def get_shop() -> dict:
    load_sample_shop()
    return store.get("shop", "main")


def get_products() -> list[dict]:
    load_sample_shop()
    return sorted(store.all("products"), key=lambda p: p["id"])


def get_product(product_id: str) -> dict | None:
    p = store.get("products", product_id)
    return dict(p, id=product_id) if p else None


def get_faqs() -> list[dict]:
    load_sample_shop()
    return store.all("faqs")


def shop_info_text() -> str:
    """Shop data as compact text for prompts."""
    s = get_shop()
    lines = [
        f"Shop: {s['name']} ({s.get('city', '')})",
        f"Timings: {s.get('timings', '')}",
        f"Delivery areas: {', '.join(s.get('delivery_areas', []))}. Delivery fee: Rs {s.get('delivery_fee', 0)}",
        f"Notice: {s.get('min_order_notice', '')}",
        f"Payment: {', '.join(s.get('payment_methods', []))}",
        f"Policies: {s.get('policies', '')}",
        "Products:",
    ]
    for p in get_products():
        stock = "in stock" if p.get("in_stock", True) else "OUT OF STOCK"
        lines.append(f"- [{p['id']}] {p['name']}: Rs {p['price']:,} ({stock})")
    lines.append("FAQ:")
    for f in get_faqs():
        lines.append(f"- Q: {f['question']} A: {f['answer']}")
    return "\n".join(lines)


# ------------------------------------------------------------------ customers
def get_customer(phone: str) -> dict | None:
    return store.get("customers", phone)


def upsert_customer(phone: str, fields: dict) -> None:
    store.update("customers", phone, dict(fields, phone=phone))


def list_customers() -> list[dict]:
    return store.all("customers")


# ------------------------------------------------------------------ conversations
def get_conversation(phone: str) -> dict:
    conv = store.get("conversations", phone)
    if not conv:
        conv = {"customer_phone": phone, "messages": [], "ai_paused": False, "language": None,
                "draft_order": None, "discounts": {}, "updated_at": now_iso()}
        store.set("conversations", phone, conv)
    return conv


def save_conversation(phone: str, conv: dict) -> None:
    conv["updated_at"] = now_iso()
    store.set("conversations", phone, {k: v for k, v in conv.items() if k != "id"})


def add_message(phone: str, role: str, text: str, meta: dict | None = None) -> None:
    conv = get_conversation(phone)
    conv["messages"].append({"role": role, "text": text, "meta": meta or {}, "at": now_iso()})
    save_conversation(phone, conv)


def list_conversations() -> list[dict]:
    return sorted(store.all("conversations"), key=lambda c: c.get("updated_at", ""), reverse=True)


# ------------------------------------------------------------------ orders, bookings, flags
def save_order(order: dict) -> str:
    oid = order.get("id") or new_id("ord")
    store.set("orders", oid, {k: v for k, v in order.items() if k != "id"})
    return oid


def get_order(order_id: str) -> dict | None:
    o = store.get("orders", order_id)
    return dict(o, id=order_id) if o else None


def update_order(order_id: str, fields: dict) -> None:
    store.update("orders", order_id, fields)


def list_orders() -> list[dict]:
    return sorted(store.all("orders"), key=lambda o: o.get("created_at", ""), reverse=True)


def save_booking(booking: dict) -> str:
    bid = new_id("bk")
    store.set("bookings", bid, booking)
    return bid


def list_bookings() -> list[dict]:
    return sorted(store.all("bookings"), key=lambda b: b.get("date_time", ""))


def add_flag(flag_type: str, phone: str, reason: str, order_id: str | None = None) -> str:
    fid = new_id("flag")
    store.set("flags", fid, {"type": flag_type, "customer_phone": phone, "reason": reason,
                             "order_id": order_id, "resolved": False, "created_at": now_iso()})
    return fid


def list_flags(include_resolved: bool = False) -> list[dict]:
    flags = store.all("flags")
    if not include_resolved:
        flags = [f for f in flags if not f.get("resolved")]
    return sorted(flags, key=lambda f: f.get("created_at", ""), reverse=True)


def resolve_flag(flag_id: str) -> None:
    store.update("flags", flag_id, {"resolved": True})


# ------------------------------------------------------------------ usage (credit protection)
def add_usage(amounts: dict) -> None:
    """Add to today's counters: messages, ai_calls, tokens, cost_usd, per-model numbers."""
    try:
        store.incr("usage", today_key(), amounts)
    except Exception:  # usage tracking must never break a customer reply
        pass


def get_usage(day: str | None = None) -> dict:
    return store.get("usage", day or today_key()) or {}


def list_usage() -> list[dict]:
    return sorted(store.all("usage"), key=lambda u: u["id"], reverse=True)
