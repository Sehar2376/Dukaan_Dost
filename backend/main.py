"""Dukaan Dost backend. Run:  uvicorn main:app --reload   then open http://localhost:8000/docs"""
import os
import re
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import agent
import ai
import db
import market
import summary

app = FastAPI(title="Dukaan Dost API", version="0.6.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FALLBACK_REPLY = "Thori der mein reply karte hain."
LIMIT_REPLY = "Aaj ke messages ki limit poori ho gayi. Owner jald aap se rabta karein ge."
BUSY_REPLY = "Abhi bohat zyada messages aa rahe hain. Owner jald aap se rabta karein ge."
ABUSE_REPLY = "Hum aap ki madad ke liye hazir hain. Meharbani kar ke ehtiram se baat karein."
MEDIA_REPLY = "Abhi sirf text messages samajh sakte hain. Meharbani kar ke type kar dein."
NEEDS_OWNER = "[NEEDS_OWNER]"
DAILY_LIMIT = int(os.getenv("DAILY_MESSAGE_LIMIT", "40"))      # per phone number per day
TOTAL_DAILY_LIMIT = int(os.getenv("TOTAL_DAILY_LIMIT", "500"))  # whole app per day
AGENT_INTENTS = {"order", "booking", "bargain", "complaint"}

# One message at a time per phone number, so fast double-messages don't overwrite each other.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def phone_lock(phone: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(phone, threading.Lock())


# ======================================================================= customer chat
class ChatIn(BaseModel):
    phone: str = Field(..., examples=["03001234567"], max_length=20)
    message: str = Field(..., examples=["Delivery charges kitne hain?"], max_length=1000)


class ChatOut(BaseModel):
    reply: str
    language: str
    intent: str
    urgent: bool
    needs_owner: bool = False
    ai_paused: bool = False
    order_summary: dict | None = None
    tools_used: list[str] = []
    route: list[str] = []  # which models handled it, e.g. ["nano", "super"] (shown in the dashboard)
    ms: int = 0            # time taken in milliseconds


@app.get("/")
def health():
    return {"status": "ok", "mock_ai": ai.MOCK, "firestore": db.USING_FIRESTORE, "database": db.database_mode(),
            "tavily": market.TAVILY_READY, "whatsapp": twilio_ready(),
            "nano": ai.NANO, "super": ai.SUPER, "ultra": ai.ULTRA}


def count_message(phone: str) -> tuple[int, int]:
    """Count this message; return (messages today from this phone, messages today in total)."""
    day = db.today_key()
    db.store.incr("usage_phones", f"{day}_{phone}", {"messages": 1})
    db.add_usage({"messages": 1})
    per_phone = (db.store.get("usage_phones", f"{day}_{phone}") or {}).get("messages", 0)
    return per_phone, db.get_usage().get("messages", 0)


def handle_message(phone: str, message: str) -> ChatOut:
    """The whole brain: used by the web chat AND the WhatsApp webhook."""
    import time

    start = time.perf_counter()
    with phone_lock(phone):
        out = _handle(phone, message)
    out.ms = round((time.perf_counter() - start) * 1000)
    return out


def _simple(reply: str, language: str = "roman_urdu", intent: str = "other", **kw) -> ChatOut:
    return ChatOut(reply=reply, language=language, intent=intent, urgent=False, **kw)


def _mid_order(conv: dict, intent: str) -> bool:
    """True when the agent talked to this customer in the last 30 minutes and the new message isn't
    abuse. Example: 'Ayesha, House 12, Gulshan, cash' or 'Sham 7 baje' alone looks like 'other' (Nano
    sometimes even says 'greeting'), but it is the answer to the agent's question, so it must go back
    to the agent, not to the FAQ path."""
    if intent == "abuse" or not conv.get("agent_at"):
        return False
    from datetime import datetime, timezone

    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(conv["agent_at"])).total_seconds() < 1800
    except ValueError:
        return False


PRODUCT_ID = re.compile(r"[ \t]*\[p\d+\]")
# "Menu bhej dein", "Chocolate cake kitne ka hai?", "rate list", "قیمت" (not "kitne din pehle")
PRICE_QUESTION = re.compile(r"\b(menu|price|prices|rate|rates|qeemat|keemat|kimat|cost)\b|\bkitne? k[ai]\b|"
                            r"\bkitnay k[ai]\b|\bkitna\s+(?:hai|hy|he)\b|قیمت|مینو|ریٹ", re.IGNORECASE)
MENU_HEADER = {"urdu": "جی، ہمارا مینو یہ ہے:", "english": "Here is our menu:"}
MENU_FOOTER = {"urdu": "ڈیلیوری: Rs {fee:,}", "english": "Delivery: Rs {fee:,}"}


def menu_reply(language: str) -> str:
    """The menu with prices, written by code straight from the saved products (always correct)."""
    shop = db.get_shop()
    lines = [f"- {p['name']}: Rs {p['price']:,}" for p in db.get_products() if p.get("in_stock", True)]
    head = MENU_HEADER.get(language, "Ji, hamara menu yeh hai:")
    foot = MENU_FOOTER.get(language, "Delivery: Rs {fee:,}").format(fee=int(shop.get("delivery_fee", 0) or 0))
    return "\n".join([head, *lines, foot])


CONFIRM_WORDS = re.compile(r"\b(confirm|confirmed|order kar|order kardo|order kar do|book kar|place kar)\b|کنفرم",
                           re.IGNORECASE)


# Times, addresses, names and payment in a message are order details: only the order agent checks them in
# code (shop hours, notice, delivery area). The FAQ path must never answer "raat 11 baje deliver kar dein ge".
ORDER_DETAIL = re.compile(r"\b(\d{1,2}\s*(?:baje|bjay|bje|am|pm)|kal|parson|aaj|subah|shaam|sham|raat|dopahar|"
                          r"address|house|block|street|gali|flat|naam|name|cash|cod|jazzcash|easypaisa|"
                          r"cancel)\b", re.IGNORECASE)


# "Easypaisa chalega?", "Bank transfer lete hain?", "Card accept karte ho?": answered by code from the saved
# payment methods (the AI once said yes to methods the shop doesn't take).
PAYMENT_NAMES = {"easypaisa": "Easypaisa", "jazzcash": "JazzCash", "jazz cash": "JazzCash", "bank": "bank transfer",
                 "card": "card", "cash": "cash on delivery", "cod": "cash on delivery"}
PAYMENT_QUESTION = re.compile(r"\b(easypaisa|jazz ?cash|bank|card|cash|cod|payment)\b.*(\?|chale|chalta|chalti|"
                              r"lete|leti|accept|hota|hoti|ho ga|hoga)|\b(payment|pay)\b.*\b(kaise|kis|kya)\b",
                              re.IGNORECASE)


# "Koi offer hai?", "Any deal?", "sale chal rahi hai?": answered by code from the saved loyalty reward.
# Asking for a lower price ("kam karo", "discount do") is bargaining and still goes to the agent.
OFFER_QUESTION = re.compile(r"\b(offers?|deals?|sale|promotion|koi discount hai|discount hai kya)\b", re.IGNORECASE)


def offer_reply(language: str) -> str:
    shop = db.get_shop()
    every, pct = int(shop.get("loyalty_every", 5) or 0), float(shop.get("loyalty_percent", 10) or 0)
    if every < 2 or pct <= 0:
        return "There are no offers right now." if language == "english" else "Ji, abhi koi offer nahi chal raha."
    if language == "english":
        return f"Yes! Every {every}th order gets {pct:g}% off. What would you like to order?"
    return f"Ji haan! Har {every}th order pe {pct:g}% discount milta hai. Aap kya order karna chahenge?"


def payment_reply(message: str, language: str) -> str:
    methods = db.get_shop().get("payment_methods", [])
    listed = ", ".join(methods) or "cash on delivery"
    have = " ".join(methods).lower().replace(" ", "")
    asked = [name for key, name in PAYMENT_NAMES.items() if key in message.lower()]
    missing = [a for a in dict.fromkeys(asked) if a.lower().replace(" ", "").split("on")[0][:4] not in have]
    if language == "english":
        head = f"Sorry, we don't take {missing[0]} yet. " if missing else ""
        return f"{head}You can pay by: {listed}."
    head = f"Maaf kijiye, {missing[0]} abhi nahi lete. " if missing else "Ji, "
    return f"{head}Payment ke liye: {listed}."


def names_a_product(message: str) -> bool:
    """A short message that is just a product ("Chocolate", "nan khatai") continues an order: the agent handles it."""
    words = [w for w in re.findall(r"\w+", message.lower()) if len(w) > 2]
    if not words or len(words) > 3:
        return False
    names = " ".join(p["name"].lower() for p in db.get_products())
    return any(w in names for w in words)


def looks_like_confirm(message: str) -> bool:
    """'Haan, confirm' or 'ji kar dein' must always reach the order agent, which checks for a saved order in
    code. The FAQ path can't see orders, so it must never be the one to answer (it could wrongly say
    'order confirm ho gaya')."""
    import tools

    text = message.strip()
    return bool(CONFIRM_WORDS.search(text)) or (len(text.split()) <= 4 and bool(tools.YES.search(text.lower())))


def _handle(phone: str, message: str) -> ChatOut:
    db.add_message(phone, "customer", message)
    conv = db.get_conversation(phone)

    if conv["ai_paused"]:  # owner took over (F6): AI stays quiet
        return _simple("", conv["language"] or "roman_urdu", ai_paused=True)

    # ---- credit protection: no AI call at all when a limit is reached
    per_phone, total = count_message(phone)
    if per_phone > DAILY_LIMIT:
        return _simple(LIMIT_REPLY)
    if total > TOTAL_DAILY_LIMIT or (not ai.MOCK and ai.over_budget()):
        if not db.get_usage().get("budget_flagged"):  # alert the owner once per day
            db.add_flag("urgent", phone, "Daily AI limit reached - assistant paused until tomorrow")
            db.add_usage({"budget_flagged": 1})
        db.add_message(phone, "assistant", BUSY_REPLY)
        return _simple(BUSY_REPLY, needs_owner=True)

    info = ai.classify(message)  # Nemotron Nano
    conv = db.get_conversation(phone)
    conv["language"] = info["language"]
    db.save_conversation(phone, conv)
    needs_owner, order_summary, used = False, None, []
    route = ["nano"]  # Nano always reads the message first
    shop = db.get_shop()

    if info["intent"] == "abuse":  # stay polite, don't spend more AI, tell the owner
        db.add_flag("abuse", phone, message[:160])
        db.add_message(phone, "assistant", ABUSE_REPLY, info)
        return ChatOut(reply=ABUSE_REPLY, needs_owner=True, route=["nano"],
                       **{k: info[k] for k in ("language", "intent", "urgent")})

    if OFFER_QUESTION.search(message) and not conv.get("draft_order") and not agent.asked_for_discount(phone):
        reply = offer_reply(info["language"])
        db.add_message(phone, "assistant", reply, {**info, "route": route})
        return ChatOut(reply=reply, language=info["language"], intent=info["intent"], urgent=info["urgent"], route=route)
    if PAYMENT_QUESTION.search(message) and not conv.get("draft_order"):
        reply = payment_reply(message, info["language"])
        db.add_message(phone, "assistant", reply, {**info, "route": route})
        return ChatOut(reply=reply, language=info["language"], intent=info["intent"], urgent=info["urgent"], route=route)

    try:
        if (info["intent"] in AGENT_INTENTS or conv.get("draft_order") or _mid_order(conv, info["intent"])
                or looks_like_confirm(message) or ORDER_DETAIL.search(message) or names_a_product(message)
                or agent.asked_for_discount(phone)):  # "discount do", "thora kam kar dein": always the bargaining agent
            route.append("super")
            result = agent.run_agent(phone, info["language"], info["intent"])  # Nemotron Super + tools
            c = db.get_conversation(phone)
            c["agent_at"] = db.now_iso()  # remember: this customer is in the middle of an order/booking
            db.save_conversation(phone, c)
            reply, order_summary, used = result["reply"], result["order_summary"], result["tools_used"]
        else:
            # our fixed "owner will confirm" lines are left out: a chat full of them makes Nano copy them
            recent = [m for m in conv["messages"][:-1] if m["role"] in ("customer", "assistant", "owner")
                      and m["text"] not in ai.OWNER_WILL_CONFIRM.values()][-6:]
            history = "\n".join(f"{'Customer' if m['role'] == 'customer' else ('Owner' if m['role'] == 'owner' else 'Shop')}: "
                                f"{m['text'][:300]}" for m in recent)
            owner_said = "\n".join(agent.owner_messages(phone))
            extra = {"owner_said": owner_said} if owner_said else {}  # only after an owner takeover
            reply = ai.answer_faq(message, info["language"], db.shop_info_text(), shop["name"],
                                  shop.get("city", ""), history=history, **extra)
            if NEEDS_OWNER in reply and PRICE_QUESTION.search(message):
                reply = menu_reply(info["language"])  # a price/menu question is answered from the database, never guessed
    except RuntimeError:
        reply, needs_owner = FALLBACK_REPLY, True
        db.add_flag("urgent", phone, "AI service error - please reply manually")

    if NEEDS_OWNER in reply:
        reply, needs_owner = reply.replace(NEEDS_OWNER, "").strip(), True
        db.add_flag("question", phone, f"Question the assistant could not answer: {message[:120]}")
    if "flag_owner" in used:  # the agent already alerted the owner
        needs_owner = True
    elif info["intent"] == "complaint" or (info["urgent"] and info["intent"] not in ("greeting", "faq")):
        db.add_flag("complaint" if info["intent"] == "complaint" else "urgent", phone, message[:160])
        needs_owner = True
    reply = PRODUCT_ID.sub("", reply).strip()  # never show internal ids like [p1] to the customer
    reply = agent.polish_reply(reply, info["language"])  # one voice, readable dates, no fake menu changes
    if not reply:
        reply = FALLBACK_REPLY

    reply = agent.limit_thanks(reply, order_saved="confirm_order" in used)  # thank once, only after an order
    if ai.MOCK:
        route = ["practice"]  # no API key: rules in practice.py answered, not Nemotron
    db.add_message(phone, "assistant", reply, {**info, "tools_used": used, "route": route})
    return ChatOut(reply=reply, language=info["language"], intent=info["intent"], urgent=info["urgent"],
                   needs_owner=needs_owner, order_summary=order_summary, tools_used=used, route=route)


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    return handle_message(body.phone.strip(), body.message.strip())


@app.get("/usage")
def usage():
    """Today's AI usage and estimated cost, plus earlier days. For the owner / team only."""
    today = db.get_usage()
    return {"today": db.today_key(), "messages": today.get("messages", 0), "ai_calls": today.get("ai_calls", 0),
            "prompt_tokens": today.get("prompt_tokens", 0), "completion_tokens": today.get("completion_tokens", 0),
            "estimated_cost_usd": round(today.get("cost_usd", 0), 4),
            "by_model": {t: {"calls": today.get(f"{t}_calls", 0), "cost_usd": round(today.get(f"{t}_cost_usd", 0), 4)}
                         for t in ("nano", "super", "ultra")},
            "tavily_searches": today.get("tavily_calls", 0),
            # What the same tokens would have cost if every call used Nemotron Ultra (the "no routing" baseline)
            "baseline_all_ultra_usd": round(today.get("prompt_tokens", 0) / 1e6 * ai.PRICES["ultra"][0]
                                            + today.get("completion_tokens", 0) / 1e6 * ai.PRICES["ultra"][1], 4),
            "limits": {"per_phone_per_day": DAILY_LIMIT, "total_per_day": TOTAL_DAILY_LIMIT,
                       "daily_budget_usd": ai.DAILY_BUDGET_USD, "tavily_per_day": market.TAVILY_DAILY_LIMIT},
            "history": [{"date": u["id"], "messages": u.get("messages", 0),
                         "estimated_cost_usd": round(u.get("cost_usd", 0), 4)} for u in db.list_usage()[:14]]}


# ======================================================================= WhatsApp (Twilio)
def twilio_ready() -> bool:
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))


def valid_twilio_request(request: Request, params: dict) -> bool:
    """Reject fake requests: Twilio signs every webhook with your auth token."""
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not token or os.getenv("TWILIO_VALIDATE", "1") == "0":
        return True  # not configured yet (local testing)
    from twilio.request_validator import RequestValidator

    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")  # e.g. https://dukaan-dost-api.onrender.com
    url = f"{base}{request.url.path}" if base else str(request.url)
    return RequestValidator(token).validate(url, params, request.headers.get("X-Twilio-Signature", ""))


def process_whatsapp(phone: str, text: str) -> None:
    """Runs after we've already answered Twilio, so slow AI replies never time out."""
    reply = handle_message(phone, text).reply
    if reply:
        send_whatsapp(phone, reply)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    """Twilio calls this for every incoming WhatsApp message."""
    from fastapi.concurrency import run_in_threadpool
    from twilio.twiml.messaging_response import MessagingResponse

    params = dict(await request.form())
    if not valid_twilio_request(request, params):
        raise HTTPException(403, "Invalid Twilio signature")
    phone = params.get("From", "").replace("whatsapp:", "")
    body = (params.get("Body") or "").strip()[:1000]
    twiml = MessagingResponse()

    if params.get("NumMedia", "0") != "0" and not body:
        twiml.message(MEDIA_REPLY)
    elif twilio_ready():
        background.add_task(process_whatsapp, phone, body)  # answer Twilio now, reply in a moment
    else:  # Twilio REST not configured: reply inside the webhook (may time out on slow replies)
        reply = (await run_in_threadpool(handle_message, phone, body)).reply
        if reply:
            twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")


def send_whatsapp(phone: str, text: str) -> bool:
    """Owner's manual reply to a real WhatsApp number (only if Twilio is configured)."""
    sid, token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    sender = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    if not (sid and token and phone.startswith("+")):
        return False
    from twilio.rest import Client
    try:
        Client(sid, token).messages.create(from_=sender, to=f"whatsapp:{phone}", body=text)
        return True
    except Exception as e:  # log, don't crash; the web dashboard still shows the chat
        print(f"Twilio send failed for {phone}: {e}")
        return False


# ======================================================================= owner: chats
def masked(phone: str) -> str:
    return agent.mask(phone)


@app.get("/conversations")
def list_conversations():
    out = []
    for c in db.list_conversations():
        last = c["messages"][-1] if c["messages"] else None
        out.append({"phone": c["id"], "phone_masked": masked(c["id"]), "ai_paused": c.get("ai_paused", False),
                    "language": c.get("language"), "last_message": last, "updated_at": c.get("updated_at")})
    return out


@app.get("/conversations/{phone}")
def get_conversation(phone: str):
    return dict(db.get_conversation(phone), phone_masked=masked(phone))


@app.post("/conversations/{phone}/takeover")
def takeover(phone: str, paused: bool = True):
    conv = db.get_conversation(phone)
    conv["ai_paused"] = paused
    db.save_conversation(phone, conv)
    return {"phone": phone, "ai_paused": paused}


class OwnerReply(BaseModel):
    text: str


@app.post("/conversations/{phone}/reply")
def owner_reply(phone: str, body: OwnerReply):
    db.add_message(phone, "owner", body.text)
    sent = send_whatsapp(phone, body.text)
    return {"ok": True, "sent_to_whatsapp": sent}


# ======================================================================= owner: orders etc.
@app.get("/orders")
def list_orders(status: str | None = None):
    orders = db.list_orders()
    if status:
        orders = [o for o in orders if o.get("status") == status]
    return [dict(o, phone_masked=masked(o["customer_phone"])) for o in orders]


class OrderStatus(BaseModel):
    status: str = Field(..., examples=["delivered"])  # new | confirmed | delivered | cancelled


@app.patch("/orders/{order_id}")
def update_order_status(order_id: str, body: OrderStatus):
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if body.status not in ("new", "confirmed", "delivered", "cancelled"):
        raise HTTPException(400, "Bad status")
    old = order.get("status")
    db.update_order(order_id, {"status": body.status})
    c = db.get_customer(order["customer_phone"]) or {}
    if body.status == "delivered" and old != "delivered":
        db.upsert_customer(order["customer_phone"], {"completed_orders": c.get("completed_orders", 0) + 1})
    if body.status == "cancelled" and old != "cancelled":
        db.upsert_customer(order["customer_phone"], {"cancelled_orders": c.get("cancelled_orders", 0) + 1})
    return {"ok": True, "order_id": order_id, "status": body.status}


@app.get("/bookings")
def list_bookings():
    return [dict(b, phone_masked=masked(b["customer_phone"])) for b in db.list_bookings()]


@app.get("/customers")
def list_customers():
    return [dict(c, phone=masked(c["id"]), id=c["id"]) for c in db.list_customers()]


@app.get("/flags")
def list_flags(include_resolved: bool = False):
    return [dict(f, phone_masked=masked(f["customer_phone"])) for f in db.list_flags(include_resolved)]


@app.post("/flags/{flag_id}/resolve")
def resolve_flag(flag_id: str):
    db.resolve_flag(flag_id)
    return {"ok": True}


# ======================================================================= owner: 5-minute setup
class SetupText(BaseModel):
    text: str = Field(..., examples=["Chocolate cake 1kg 2200 (cost 1400) max 10% off. Delivery Rs 200 Gulshan, DHA. 10am-9pm"])


@app.get("/setup")
def current_setup():
    return {"shop": db.get_shop(), "products": db.get_products(), "faqs": db.get_faqs()}


@app.post("/setup/parse")
def setup_parse(body: SetupText):
    try:
        data = ai.parse_shop_text(body.text)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(502, f"Could not read the text, please try again ({e})")
    warnings = []
    for p in data.get("products", []):
        if not p.get("price"):
            warnings.append(f"Price missing for {p.get('name')}")
        if p.get("cost_price") in (None, 0, ""):
            warnings.append(f"Cost price missing for {p.get('name')}")
    return {**data, "warnings": warnings}


class SetupSave(BaseModel):
    shop: dict
    products: list[dict]
    faqs: list[dict] = []


class StockIn(BaseModel):
    in_stock: bool


@app.patch("/products/{product_id}")
def set_stock(product_id: str, body: StockIn):
    """One tap in Settings: mark an item sold out (or available again) without pasting the whole menu.
    The assistant reads in_stock on every message, so customers are told right away."""
    if not db.get_product(product_id):
        raise HTTPException(404, "Product not found")
    db.store.update("products", product_id, {"in_stock": body.in_stock})
    return db.get_product(product_id)


@app.post("/setup/save")
def setup_save(body: SetupSave):
    for p in body.products:
        if not p.get("name") or not isinstance(p.get("price"), (int, float)):
            raise HTTPException(400, f"Every product needs a name and a numeric price: {p}")
        if p.get("cost_price") in (None, ""):
            p["cost_price"] = 0
        if p.get("in_stock") is None:
            p["in_stock"] = True
        p.pop("id", None)  # ids are re-numbered p1, p2, ... on save
        p["max_discount_percent"] = max(0, min(50, float(p.get("max_discount_percent") or 0)))
    # loyalty reward: every Nth order gets X% off (0 = off). Kept small so the owner never loses money by mistake.
    body.shop["loyalty_every"] = max(0, min(50, int(body.shop.get("loyalty_every", 5) or 0)))
    body.shop["loyalty_percent"] = max(0, min(30, float(body.shop.get("loyalty_percent", 10) or 0)))
    db.save_catalog(body.shop, body.products, body.faqs)
    db.store.delete_all("market")  # product ids change on save, so old price checks no longer match
    return {"ok": True, "products": len(body.products), "faqs": len(body.faqs)}


# ======================================================================= owner: summaries
@app.get("/summary/daily")
def summary_daily(date: str | None = None, language: str = "roman_urdu"):
    return summary.daily(date, language)


@app.get("/summary/monthly")
def summary_monthly(month: str | None = None, language: str = "roman_urdu"):
    return summary.monthly(month, language)


# ======================================================================= owner: AI business advice (Ultra)
@app.get("/advice/monthly")
def advice_monthly(month: str | None = None, language: str = "english", refresh: bool = False):
    """Nemotron 3 Ultra reads this month's numbers and gives 3-5 tips.

    Runs only when the owner asks, and the answer is saved, so opening the page again is free.
    Use refresh=true to ask Ultra again (for example after more orders came in)."""
    month = month or db.now_karachi().strftime("%Y-%m")
    key = f"{month}_{language}"
    cached = db.store.get("advice", key)
    if cached and not refresh:
        return {**cached, "cached": True}
    if not ai.MOCK and ai.over_budget():
        if cached:
            return {**cached, "cached": True, "note": "Daily AI budget reached; showing the last advice."}
        raise HTTPException(429, "Daily AI budget reached. Try again tomorrow.")

    numbers = summary.insights(month)
    checks = market.for_advice()
    if checks:  # Tavily price checks the owner ran: lets Ultra give pricing advice too
        numbers["market_prices"] = checks
    if numbers["totals"]["orders"] == 0:
        return {"month": month, "headline": "No orders yet this month.", "tips": [], "numbers": numbers,
                "model_used": None, "cached": False}
    try:
        advice = ai.business_advice(numbers, f"the month {month}", language)
    except RuntimeError:
        if cached:
            return {**cached, "cached": True, "note": "AI is busy; showing the last advice."}
        raise HTTPException(502, "Could not get advice right now. Please try again in a minute.")
    result = {"month": month, **advice, "numbers": numbers, "generated_at": db.now_iso()}
    db.store.set("advice", key, result)
    return {**result, "cached": False}


# ======================================================================= owner: market price check (Tavily)
class MarketIn(BaseModel):
    product_id: str = Field(..., examples=["p1"])
    language: str = "english"
    refresh: bool = False


@app.post("/market/check")
def market_check(body: MarketIn):
    """Tavily searches the web for this product's price in the shop's city, Nemotron Super reads the
    results, Python compares with the owner's price. Saved for 24 hours (refresh=true searches again)."""
    try:
        return market.check(body.product_id, body.language, body.refresh)
    except market.MarketError as e:
        raise HTTPException(429 if "limit" in str(e) or "budget" in str(e) else 400 if "not found" in str(e) else 502,
                            str(e))


@app.get("/market/checks")
def market_checks():
    """All saved price checks, newest first."""
    return market.saved_checks()


# ======================================================================= owner: nightly report (background job)
@app.post("/admin/run-daily-report")
def run_daily_report(day: str | None = None):
    """Make today's owner report now (the same thing the nightly Nebius Serverless Job does)."""
    import daily_report

    return daily_report.run(day)


@app.get("/reports")
def list_reports():
    """Saved nightly reports, newest first."""
    return sorted(db.store.all("reports"), key=lambda r: r.get("date", ""), reverse=True)[:30]


# ======================================================================= demo helper
@app.post("/admin/reset-demo")
def reset_demo():
    """Reload the demo shop (does not delete orders)."""
    db.load_sample_shop(force=True)
    return {"ok": True}


@app.post("/admin/load-demo")
def load_demo(days: int = Query(90, ge=7, le=120)):
    """Fill the database the server is using with DEMO data: the bakery, 20 customers and orders
    for the last `days` days. Works with Firestore AND with the in-memory database (no Firebase).
    Warning: deletes existing orders, customers, chats, bookings and flags first."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "sample_data"))
    import load_sample

    load_sample.main(days=days)
    return {"ok": True, "orders": len(db.list_orders()), "customers": len(db.list_customers()),
            "database": {"firestore": "firestore", "backup": "backup memory (Firebase quota reached; temporary)",
                         "memory": "memory (lost when the server stops)"}[db.database_mode()]}
