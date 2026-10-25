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
    """Firestore with a short in-memory cache per collection.

    The dashboard refreshes every 30-60 s and many endpoints list whole collections (orders,
    flags...). Without a cache every refresh reads every document, which quickly uses up
    Firestore's free daily read quota. Reads of a whole collection are reused for
    FIRESTORE_CACHE_SECONDS (default 120) and our own writes update the cache, so the data
    this server shows stays correct. Another server instance may lag by up to that time."""

    def __init__(self, cred_path):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            # cred_path is a file path, or (on Vercel) the whole JSON text of the key
            key = json.loads(cred_path) if cred_path.startswith("{") else cred_path
            firebase_admin.initialize_app(credentials.Certificate(key))
        self.fs = firestore.client()
        self._setup_cache()

    def _setup_cache(self):
        import threading

        self.ttl = float(os.getenv("FIRESTORE_CACHE_SECONDS", "120"))
        self._cache = {}  # col -> (time loaded, {doc_id: data})
        self._lock = threading.Lock()

    def __getattr__(self, name):  # cache set up lazily (e.g. when a test skips __init__)
        if name in ("ttl", "_cache", "_lock"):
            self._setup_cache()
            return getattr(self, name)
        raise AttributeError(name)

    def _cached(self, col):
        import time

        hit = self._cache.get(col)
        return hit[1] if hit and time.time() - hit[0] < self.ttl else None

    def _forget(self, col, doc_id=None):
        self._cache.pop(col, None)
        if doc_id is not None:
            self._cache.pop((col, doc_id), None)

    def get(self, col, doc_id):
        import time

        # Only data that rarely changes (shop, menu, FAQs...) is reused for single reads. Chats, orders and
        # usage are always read fresh, so two server copies never overwrite each other's new messages.
        static = col in STATIC_COLLECTIONS
        if static:
            with self._lock:
                docs = self._cached(col)
                if docs is not None and doc_id in docs:
                    return dict(docs[doc_id])
                hit = self._cache.get((col, doc_id))
                if hit and time.time() - hit[0] < self.ttl:
                    return dict(hit[1]) if hit[1] is not None else None
        snap = self.fs.collection(col).document(doc_id).get()
        value = snap.to_dict() if snap.exists else None
        if static:
            with self._lock:
                self._cache[(col, doc_id)] = (time.time(), value)
        return dict(value) if value is not None else None

    def set(self, col, doc_id, value):
        import time

        self.fs.collection(col).document(doc_id).set(value)
        with self._lock:
            docs = self._cached(col)
            if docs is not None:
                docs[doc_id] = dict(value)
            if (col, doc_id) in self._cache:
                self._cache[(col, doc_id)] = (time.time(), dict(value))

    def update(self, col, doc_id, fields):
        self.fs.collection(col).document(doc_id).set(fields, merge=True)
        with self._lock:
            docs = self._cached(col)
            if docs is not None and doc_id in docs:
                docs[doc_id].update(fields)
            else:
                self._cache.pop(col, None)
            self._cache.pop((col, doc_id), None)

    def all(self, col):
        import time

        with self._lock:
            docs = self._cached(col)
            if docs is not None:
                return [dict(v, id=k) for k, v in docs.items()]
        docs = {s.id: s.to_dict() for s in self.fs.collection(col).stream()}
        with self._lock:
            self._cache[col] = (time.time(), docs)
        return [dict(v, id=k) for k, v in docs.items()]

    def delete_all(self, col):
        import time

        for s in self.fs.collection(col).stream():
            s.reference.delete()
        with self._lock:
            self._cache = {k: v for k, v in self._cache.items() if not (isinstance(k, tuple) and k[0] == col)}
            self._cache[col] = (time.time(), {})

    def incr(self, col, doc_id, amounts):
        from firebase_admin import firestore

        self.fs.collection(col).document(doc_id).set(
            {k: firestore.Increment(v) for k, v in amounts.items()}, merge=True)
        with self._lock:
            self._forget(col, doc_id)


# Collections that change rarely, so single reads may be reused for FIRESTORE_CACHE_SECONDS.
STATIC_COLLECTIONS = {"shop", "products", "faqs", "advice", "market", "reports"}


def _is_quota_error(e: Exception) -> bool:
    return type(e).__name__ == "ResourceExhausted" or "RESOURCE_EXHAUSTED" in str(e) or "Quota exceeded" in str(e)


class BackupStore:
    """Firestore first. If Firebase's free daily quota runs out, switch to memory (with the demo shop loaded)
    so customers still get AI replies instead of an error. Data written in backup mode is temporary.
    Firestore is tried again every BACKUP_RETRY_SECONDS (default 30 minutes)."""

    def __init__(self, primary):
        import threading

        self.primary = primary
        self.memory = MemoryStore()
        self.backup_since = None
        self.retry_after = float(os.getenv("BACKUP_RETRY_SECONDS", "1800"))
        self._seeding = False
        self._lock = threading.Lock()

    @property
    def in_backup(self) -> bool:
        return self.backup_since is not None

    def _start_backup(self, err):
        import time

        with self._lock:
            if self.backup_since is not None:
                return
            self.backup_since = time.time()
        print(f"Firestore unavailable ({type(err).__name__}): backup mode, data kept in memory for now")
        # Keep whatever this server copy already read from Firestore, then fill any gaps with the demo shop.
        for key, (_, docs) in list(getattr(self.primary, "_cache", {}).items()):
            if isinstance(key, str):
                for doc_id, value in docs.items():
                    self.memory.set(key, doc_id, dict(value))
            elif docs is not None:
                self.memory.set(key[0], key[1], dict(docs))
        self._seeding = True
        try:
            if not self.memory.get("shop", "main") or not self.memory.all("orders"):
                import sys

                sys.path.insert(0, str(Path(__file__).parent.parent / "sample_data"))
                import load_sample

                load_sample.main(days=30)
        except Exception as e:  # seeding is best effort; the shop data alone is enough to chat
            print(f"Backup demo data not fully loaded: {e}")
            if not self.memory.get("shop", "main"):
                data = json.loads(SAMPLE.read_text(encoding="utf-8"))
                save_catalog(data["shop"], data["products"], data["faqs"])
        finally:
            self._seeding = False

    def _call(self, name, *args):
        import time

        if self._seeding:
            return getattr(self.memory, name)(*args)
        if self.backup_since is not None and time.time() - self.backup_since > self.retry_after:
            self.backup_since = None  # quota may have reset: try Firestore again
        if self.backup_since is None:
            try:
                return getattr(self.primary, name)(*args)
            except Exception as e:
                if not _is_quota_error(e):
                    raise
                self._start_backup(e)
        return getattr(self.memory, name)(*args)

    def get(self, col, doc_id):
        return self._call("get", col, doc_id)

    def set(self, col, doc_id, value):
        return self._call("set", col, doc_id, value)

    def update(self, col, doc_id, fields):
        return self._call("update", col, doc_id, fields)

    def all(self, col):
        return self._call("all", col)

    def delete_all(self, col):
        return self._call("delete_all", col)

    def incr(self, col, doc_id, amounts):
        return self._call("incr", col, doc_id, amounts)


_cred = os.getenv("FIREBASE_CREDENTIALS", "").strip()
store = BackupStore(FirestoreStore(_cred)) if _cred else MemoryStore()
USING_FIRESTORE = bool(_cred)


def database_mode() -> str:
    """'firestore', 'backup' (Firebase quota reached: temporary memory) or 'memory' (no Firebase key)."""
    if getattr(store, "in_backup", False):
        return "backup"
    return "firestore" if USING_FIRESTORE else "memory"


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
