"""Tools the Nemotron Super agent can call.

GOLDEN RULE: the AI only decides WHICH tool to call. Every price, discount, total, profit
and risk score is calculated here in Python, so a customer can never talk the AI into a
bigger discount than the owner allows.

Every tool takes `phone` (added by the agent loop, not by the model) and returns a dict.
"""
import math
import re
from datetime import datetime, timedelta

import db
from risk import missing_address_parts, score_cod_order


def _match_products(search: str) -> list[dict]:
    words = [w for w in re.findall(r"[a-z0-9]+", (search or "").lower()) if len(w) > 1]
    products = db.get_products()
    if not words:
        return products
    scored = []
    for p in products:
        name = (p["name"] + " " + p.get("category", "")).lower()
        hits = sum(1 for w in words if w in name)
        if hits:
            scored.append((hits, p))
    return [p for _, p in sorted(scored, key=lambda x: -x[0])]


def _public(p: dict) -> dict:
    """What the AI may see about a product (never the cost price)."""
    return {"product_id": p["id"], "name": p["name"], "price": p["price"],
            "in_stock": p.get("in_stock", True)}


# ------------------------------------------------------------------ 1. get_products
def get_products(phone: str, search: str = "") -> dict:
    found = _match_products(search)
    if not found:
        return {"products": [], "note": "No matching product. Suggest items from the full list.",
                "all_products": [_public(p) for p in db.get_products()]}
    return {"products": [_public(p) for p in found[:6]]}


# ------------------------------------------------------------------ 2. get_customer
def get_customer(phone: str) -> dict:
    c = db.get_customer(phone)
    if not c:
        return {"returning": False}
    last = db.get_order(c["last_order_id"]) if c.get("last_order_id") else None
    return {
        "returning": True,
        "name": c.get("name"),
        "addresses": c.get("addresses", []),
        "completed_orders": c.get("completed_orders", 0),
        "last_order": {"items": last["items"], "total": last["total"]} if last else None,
        "loyalty": loyalty(phone),
    }


# ------------------------------------------------------------------ loyalty reward (checked in code)
def nth(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 11 -> 11th"""
    end = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{end}"


def loyalty(phone: str) -> dict:
    """Every Nth order gets X% off. N and X are set by the owner (shop.loyalty_every, shop.loyalty_percent).

    Counts this customer's confirmed orders that were not cancelled, so the AI can never invent a reward."""
    shop = db.get_shop()
    every = int(shop.get("loyalty_every", 5) or 0)
    pct = float(shop.get("loyalty_percent", 10) or 0)
    c = db.get_customer(phone) or {}
    past = max(0, int(c.get("total_orders", 0)) - int(c.get("cancelled_orders", 0)))
    if every < 2 or pct <= 0:
        return {"active": False, "eligible": False, "percent": 0, "order_number": past + 1}
    next_number = past + 1
    to_go = (every - next_number % every) % every  # 0 = this order gets the reward
    return {"active": True, "eligible": to_go == 0, "percent": pct if to_go == 0 else 0,
            "reward_percent": pct, "every": every, "order_number": next_number, "orders_until_reward": to_go}


# ------------------------------------------------------------------ 3. check_discount
def check_discount(phone: str, product_id: str, requested_percent: float = 0) -> dict:
    """Bargaining: 1st ask -> half of the owner's max, 2nd ask -> the max, then final."""
    p = db.get_product(product_id)
    if not p:
        return {"error": f"Unknown product_id {product_id}. Call get_products first."}
    conv = db.get_conversation(phone)
    state = conv["discounts"].get(product_id, {"attempts": 0, "percent": 0})
    state["attempts"] += 1
    max_pct = float(p.get("max_discount_percent", 0))

    if max_pct <= 0:
        offer, final = 0, True
    elif state["attempts"] == 1:
        offer, final = math.ceil(max_pct / 2), False
    else:
        offer, final = max_pct, True
    if requested_percent and 0 < requested_percent < offer:
        offer = requested_percent  # customer asked for less than we'd give
    state["percent"] = offer
    conv["discounts"][product_id] = state
    db.save_conversation(phone, conv)

    reward = loyalty(phone)
    best = max(offer, reward["percent"])  # loyalty reward and bargaining never add up: the bigger one wins
    new_price = round(p["price"] * (1 - best / 100))
    result = {"product_id": product_id, "name": p["name"], "original_price": p["price"],
              "discount_percent": best, "new_price": new_price, "is_final_offer": final}
    if reward["percent"] and reward["percent"] >= offer:
        result["is_final_offer"] = True
        result["note"] = (f"This is the customer's loyalty reward order ({nth(reward['order_number'])} order): "
                          f"{reward['percent']:g}% off already applies. Bargaining does not add more on top.")
    elif state["attempts"] >= 3:
        result["note"] = "Customer keeps pushing. Politely hold this price and offer to connect the owner."
    return result


# ------------------------------------------------------------------ time rules (checked in code)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def earliest_slot(hours_needed: float) -> datetime:
    """First time that is at least `hours_needed` from now AND inside shop opening hours."""
    shop = db.get_shop()
    t = db.now_karachi() + timedelta(hours=hours_needed)
    t = t.replace(second=0, microsecond=0)
    if t.minute:
        t += timedelta(minutes=60 - t.minute)  # round up to the next full hour
    hours = shop.get("opening_hours") or {}
    if not hours:
        return t
    for _ in range(8 * 24):  # look up to 8 days ahead, hour by hour
        day = hours.get(DAYS[t.weekday()])
        if day and day[0] <= t.strftime("%H:%M") <= day[1]:
            return t
        if day and t.strftime("%H:%M") < day[0]:
            h, m = map(int, day[0].split(":"))
            opening = t.replace(hour=h, minute=m)
            if opening >= db.now_karachi() + timedelta(hours=hours_needed):
                return opening
        t += timedelta(hours=1)
    return t


def notice_hours(categories: list[str] | None = None) -> float:
    shop = db.get_shop()
    needed = float(shop.get("min_notice_hours", 0))
    for cat in categories or []:
        needed = max(needed, float(shop.get("advance_notice_hours", {}).get(cat, 0)))
    return needed


def check_time(when: str, categories: list[str] | None = None) -> tuple[str | None, str | None]:
    """Validate a delivery/booking time against shop hours and notice rules.

    Returns (normalised "YYYY-MM-DD HH:MM", None) or (None, problem for the AI to explain)."""
    shop = db.get_shop()
    now = db.now_karachi()
    try:
        dt = datetime.strptime((when or "").strip().replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None, (f"Time must be YYYY-MM-DD HH:MM (24-hour). Now it is {now:%Y-%m-%d %H:%M} ({DAYS[now.weekday()]}). "
                      "Convert what the customer said (e.g. 'kal shaam 6 baje') and call again.")
    dt = dt.replace(tzinfo=now.tzinfo)

    hours = shop.get("opening_hours")
    if hours:
        day = DAYS[dt.weekday()]
        if not hours.get(day):
            return None, f"Shop is closed on {day}. Opening hours: {hours}"
        open_t, close_t = hours[day]
        if not (open_t <= dt.strftime("%H:%M") <= close_t):
            return None, f"{dt:%H:%M} is outside shop hours on {day} ({open_t}-{close_t})."

    needed = notice_hours(categories)
    earliest = now + timedelta(hours=needed)
    if dt < earliest:
        why = f"needs {needed:g} hours notice" if needed else "is in the past"
        slot = earliest_slot(needed)
        return None, (f"Too soon: this {why}. Earliest possible delivery: {slot:%A %Y-%m-%d %H:%M}. "
                      "Offer exactly this time (or any later time in shop hours).")
    return dt.strftime("%Y-%m-%d %H:%M"), None


YES = re.compile(r"\b(haan|han|haa|ha|ji|jee|g|yes|yeah|yup|ok|okay|okk|theek|thik|confirm|confirmed|done|"
                 r"kar do|kardo|kar dein|kardein|bilkul|sure|perfect|chalo)\b|ہاں|جی|ٹھیک|کنفرم")
NO = re.compile(r"\b(nahi|nai|nahin|no|not|cancel|ruk|ruko|wait|change|badal|mat|lekin|magar|but)\b|نہیں|رکو")


def customer_confirmed(phone: str) -> bool:
    """Code-level check that the customer's LAST message really says yes."""
    msgs = [m for m in db.get_conversation(phone)["messages"] if m["role"] == "customer"]
    if not msgs:
        return False
    text = msgs[-1]["text"].lower()
    return bool(YES.search(text)) and not NO.search(text)


# ------------------------------------------------------------------ 4. preview_order
def _in_delivery_area(address: str, areas: list[str]) -> bool:
    a = address.lower()
    for area in areas:
        keywords = [w for w in re.split(r"[\s\-]+", area.lower()) if len(w) >= 3]
        if any(k in a for k in keywords):
            return True
    return False


def preview_order(phone: str, items: list[dict], customer_name: str, address: str,
                  delivery_time: str, payment_type: str = "cod") -> dict:
    """Build the order summary in code. Saved as a draft until the customer confirms."""
    shop = db.get_shop()
    conv = db.get_conversation(phone)
    reward = loyalty(phone)
    lines, problems = [], []

    for it in items or []:
        p = db.get_product(str(it.get("product_id", "")))
        qty = int(it.get("quantity", 1) or 1)
        if not p:
            problems.append(f"Unknown product_id {it.get('product_id')}")
            continue
        if not p.get("in_stock", True):
            problems.append(f"{p['name']} is out of stock")
            continue
        bargain = conv["discounts"].get(p["id"], {}).get("percent", 0)  # only what check_discount agreed
        pct = max(bargain, reward["percent"])  # loyalty reward or bargain, whichever is bigger (never both)
        unit = round(p["price"] * (1 - pct / 100))
        lines.append({"product_id": p["id"], "name": p["name"], "quantity": qty, "unit_price": unit,
                      "original_unit_price": p["price"], "discount_percent": pct,
                      "line_total": unit * qty, "line_cost": p.get("cost_price", 0) * qty})

    missing = [f for f, v in [("customer_name", customer_name), ("address", address),
                              ("delivery_time", delivery_time)] if not (v or "").strip()]
    if not lines:
        missing.append("items")
    if missing or problems:
        return {"ok": False, "missing": missing, "problems": problems,
                "note": "Ask the customer for the missing details, then call preview_order again."}

    categories = [db.get_product(line["product_id"]).get("category", "") for line in lines]
    when, time_problem = check_time(delivery_time, categories)
    if time_problem:
        return {"ok": False, "problems": [time_problem],
                "note": "Explain this to the customer and ask for another delivery time."}

    if not _in_delivery_area(address, shop.get("delivery_areas", [])):
        return {"ok": False, "problems": [f"Address is outside delivery areas: {', '.join(shop['delivery_areas'])}"]}

    subtotal = sum(line["original_unit_price"] * line["quantity"] for line in lines)
    after_discount = sum(line["line_total"] for line in lines)
    fee = shop.get("delivery_fee", 0)
    draft = {
        "customer_phone": phone, "customer_name": customer_name.strip(), "items": lines,
        "subtotal": subtotal, "discount": subtotal - after_discount, "delivery_fee": fee,
        "total": after_discount + fee, "cost_total": sum(line["line_cost"] for line in lines),
        "address": address.strip(), "delivery_time": when,
        "payment_type": "cod" if "cod" in payment_type.lower() or "cash" in payment_type.lower() else payment_type.lower(),
        "loyalty_percent": reward["percent"],
    }
    draft["profit"] = after_discount - draft["cost_total"]
    conv["draft_order"] = draft
    db.save_conversation(phone, conv)

    address_tip = missing_address_parts(address)
    loyalty_note = (f"This is their {nth(reward['order_number'])} order, so the loyalty reward ({reward['percent']:g}% off) "
                    "is included. Tell them happily. " if reward["percent"] else "")
    return {"ok": True, "summary": {k: draft[k] for k in ("items", "subtotal", "discount", "delivery_fee",
                                                          "total", "address", "delivery_time", "payment_type",
                                                          "loyalty_percent")},
            "address_incomplete": address_tip,
            "note": "Show this summary and ask the customer to confirm. " + loyalty_note
                    + ("Also ask for house/block, street and a landmark. " if address_tip else "")}


# ------------------------------------------------------------------ 5. confirm_order
def confirm_order(phone: str) -> dict:
    """Customer said yes: save the draft, score COD risk, update the customer, raise flags."""
    conv = db.get_conversation(phone)
    draft = conv.get("draft_order")
    if not draft:
        return {"ok": False, "error": "No order to confirm. Call preview_order first."}
    if not customer_confirmed(phone):
        return {"ok": False, "error": "The customer has not clearly said yes. Show the summary and ask "
                                      "'Confirm kar dein?' Call confirm_order only after a clear yes."}

    shop = db.get_shop()
    customer = db.get_customer(phone) or {}
    past = [o for o in db.list_orders() if o.get("status") != "cancelled"]
    usual = sum(o["total"] for o in past) / len(past) if past else 2500

    if draft["payment_type"] == "cod":
        risk = score_cod_order(draft["address"], draft["total"],
                               past_cancellations=customer.get("cancelled_orders", 0),
                               completed_orders=customer.get("completed_orders", 0),
                               large_order_threshold=shop.get("large_order_threshold", 8000),
                               usual_order_size=usual)
    else:
        risk = {"level": "low", "reasons": ["Paid in advance"]}

    order = dict(draft, status="new", risk_level=risk["level"], risk_reasons=risk["reasons"],
                 created_at=db.now_iso())
    try:
        order_id = db.save_order(order)
    except Exception as e:  # never tell the customer it's confirmed if the save failed
        return {"ok": False, "error": f"Could not save order: {e}"}

    addresses = customer.get("addresses", [])
    if draft["address"] not in addresses:
        addresses = [draft["address"]] + addresses
    db.upsert_customer(phone, {"name": draft["customer_name"], "addresses": addresses[:3],
                               "total_orders": customer.get("total_orders", 0) + 1,
                               "completed_orders": customer.get("completed_orders", 0),
                               "cancelled_orders": customer.get("cancelled_orders", 0),
                               "last_order_id": order_id})

    if risk["level"] == "high":
        db.add_flag("high_risk", phone, "; ".join(risk["reasons"]), order_id)
    if draft["total"] >= shop.get("large_order_threshold", 8000):
        db.add_flag("large_order", phone, f"Large order Rs {draft['total']:,}", order_id)

    conv["draft_order"], conv["discounts"] = None, {}
    db.save_conversation(phone, conv)
    return {"ok": True, "order_id": order_id, "total": draft["total"],
            "note": "Thank the customer and confirm delivery time. Never mention the risk level."}


# ------------------------------------------------------------------ 6. create_booking
def create_booking(phone: str, service: str, date_time: str, customer_name: str = "") -> dict:
    when, problem = check_time(date_time)
    if problem:
        return {"ok": False, "error": problem}
    date_time = when
    taken = [b for b in db.list_bookings() if b["date_time"] == date_time and b["status"] != "cancelled"]
    if taken:
        return {"ok": False, "error": "That slot is already booked. Ask for another time."}
    bid = db.save_booking({"customer_phone": phone, "customer_name": customer_name, "service": service,
                           "date_time": date_time, "status": "confirmed", "created_at": db.now_iso()})
    return {"ok": True, "booking_id": bid, "timings": db.get_shop().get("timings")}


# ------------------------------------------------------------------ 7. flag_owner
def flag_owner(phone: str, reason: str, flag_type: str = "urgent") -> dict:
    if flag_type not in ("urgent", "complaint", "question"):
        flag_type = "urgent"
    return {"ok": True, "flag_id": db.add_flag(flag_type, phone, reason)}


# ------------------------------------------------------------------ registry + descriptions
FUNCTIONS = {f.__name__: f for f in (get_products, get_customer, check_discount, preview_order,
                                     confirm_order, create_booking, flag_owner)}


def _tool(name, description, properties=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


TOOLS = [
    _tool("get_products", "Search the shop's products. Returns product_id, name, price, in_stock.",
          {"search": {"type": "string", "description": "words like 'chocolate cake 2kg'; empty = all"}}),
    _tool("get_customer", "Look up this customer: name, saved addresses, last order."),
    _tool("check_discount", "Call EVERY time the customer asks for a lower price. Returns the only discount you may offer.",
          {"product_id": {"type": "string"}, "requested_percent": {"type": "number"}}, ["product_id"]),
    _tool("preview_order", "Calculate the order summary and total. Call when you know items, name, address and delivery time.",
          {"items": {"type": "array", "items": {"type": "object", "properties": {
              "product_id": {"type": "string"}, "quantity": {"type": "integer"}},
              "required": ["product_id", "quantity"]}},
           "customer_name": {"type": "string"}, "address": {"type": "string"},
           "delivery_time": {"type": "string", "description": "YYYY-MM-DD HH:MM, 24-hour, shop's local time"},
           "payment_type": {"type": "string", "description": "cod, jazzcash, easypaisa or bank"}},
          ["items", "customer_name", "address", "delivery_time"]),
    _tool("confirm_order", "Save the order. Call ONLY right after the customer's message clearly says yes to the summary."),
    _tool("create_booking", "Book an appointment slot.",
          {"service": {"type": "string"}, "date_time": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
           "customer_name": {"type": "string"}}, ["service", "date_time"]),
    _tool("flag_owner", "Alert the shop owner: complaints, anger, questions you cannot answer, special requests.",
          {"reason": {"type": "string"},
           "flag_type": {"type": "string", "enum": ["urgent", "complaint", "question"]}}, ["reason"]),
]


def run_tool(name: str, args: dict, phone: str) -> dict:
    fn = FUNCTIONS.get(name)
    if not fn:
        return {"error": f"Unknown tool {name}"}
    try:
        return fn(phone=phone, **(args or {}))
    except TypeError as e:  # model sent wrong arguments
        return {"error": f"Bad arguments for {name}: {e}"}
