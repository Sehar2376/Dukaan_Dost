"""Practice-mode agent: used instead of Nemotron Super when there is NO API key (MOCK_AI).

It is NOT AI. It reads the customer's messages with simple rules (product names, "kam kar dein",
"kal shaam 6 baje", "House 12 ... Gulshan", "cash") and then calls the SAME tools the real agent uses:
check_discount, preview_order, confirm_order, create_booking, flag_owner. So the whole app — order card,
bargaining limits, COD risk, alerts, orders page, summaries — can be tested for $0 before the key arrives.
Replies start with "(practice)". With a real key, Nemotron 3 Super replaces this file completely.
"""
import re
from datetime import timedelta

import db
import tools

AREA_WORDS = r"house|h#|h\.?no|street|st\.|block|flat|apartment|apt|road|near|gali|sector|phase|plot|lane|floor|masjid"
BARGAIN = re.compile(r"kam kar|kam karein|kam kardo|discount|last price|sasta|\bless\b|\bkam\b", re.I)
BOOKING = re.compile(r"\bbook|appointment|tasting|slot|fitting|reserve", re.I)
COMPLAINT = re.compile(r"\b(late|kharab|ganda|worst|refund|complain|complaint|ghalat|wrong)\b", re.I)


def _say(text: str, used: list[str], summary: dict | None = None) -> dict:
    return {"reply": "(practice) " + text, "tools_used": used, "order_summary": summary}


# ---------------------------------------------------------------- reading the message
def find_product(text: str) -> dict | None:
    """Best matching product, only if it is clearly better than the others."""
    # real words only: "12" in "House 12" must not match "Cookies (box of 12)"; "2kg" is fine
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and not w.isdigit()]
    scored = []
    for p in db.get_products():
        name = (p["name"] + " " + p.get("category", "")).lower()
        hits = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", name))
        if hits:
            scored.append((hits, p))
    scored.sort(key=lambda x: -x[0])
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]) or scored[0][0] < 2 and len(scored) > 1:
        return None
    return scored[0][1]


def find_quantity(text: str) -> int:
    m = re.search(r"\b(\d{1,2})\s*(?:x|×|box|boxes|pcs|piece|pieces|cakes?|dozen)\b", text.lower())
    return int(m.group(1)) if m else 1


def parse_when(text: str) -> str | None:
    """'kal shaam 6 baje' / 'parson 7pm' / 'tomorrow 11am' / '2026-10-25 18:00' -> 'YYYY-MM-DD HH:MM'."""
    t = text.lower()
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ t](\d{1,2}):(\d{2})", t)
    if m:
        return f"{m.group(1)} {int(m.group(2)):02d}:{m.group(3)}"
    now = db.now_karachi()
    day = None
    if re.search(r"\b(parson|parso|parsoon|day after tomorrow)\b", t):
        day = 2
    elif re.search(r"\b(kal|tomorrow)\b", t):
        day = 1
    elif re.search(r"\b(aaj|today|tonight)\b", t):
        day = 0
    h = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(baje|bje|pm|am|o'?clock)\b", t)
    if day is None and not h:
        return None
    hour, minute = (int(h.group(1)), int(h.group(2) or 0)) if h else (18, 0)
    if h and (h.group(3) == "pm" or re.search(r"shaam|sham|raat|evening|night|dopahar|afternoon", t)) and hour < 12:
        hour += 12
    elif h and h.group(3) not in ("am",) and not re.search(r"subah|morning", t) and 1 <= hour <= 9:
        hour += 12  # "6 baje" at a bakery means 6 pm
    date = (now + timedelta(days=day or 0)).date().isoformat()
    return f"{date} {hour:02d}:{minute:02d}"


def find_name(text: str) -> str | None:
    m = re.search(r"(?:mera naam|my name is|naam|name)\s*(?:hai|is|:|-)?\s*([A-Za-z]{3,})", text, re.I)
    if m and m.group(1).lower() not in ("hai", "is"):
        return m.group(1).capitalize()
    for m in [re.match(r"^\s*([A-Z][a-z]{2,})\s*[,\-]", text), *re.finditer(r"[,.]\s*([A-Z][a-z]{2,})\s*,", text)]:
        if m and not re.fullmatch(rf"(?i)({AREA_WORDS}|cash|haan|salam|bhai|ji|thanks|please)", m.group(1)) \
                and not any(m.group(1).lower() in a.lower() for a in db.get_shop().get("delivery_areas", [])):
            return m.group(1)
    return None


def find_address(text: str) -> str | None:
    areas = "|".join(re.escape(a.split("-")[0].lower()) for a in db.get_shop().get("delivery_areas", []))
    pattern = re.compile(rf"\b({AREA_WORDS}{'|' + areas if areas else ''})", re.I)
    parts = [p.strip() for p in re.split(r"[.;\n]", text) if pattern.search(p)]
    if not parts:
        return None
    address = ", ".join(parts)
    name = find_name(text)
    if name:  # drop the name ("Ayesha, House 12 ..." -> "House 12 ...")
        address = re.sub(rf"^.*?\b{name}\b\s*[,\-]?\s*", "", address, count=1)
    address = re.sub(r"(?i)\b(cash on delivery|cod|cash)\b", "", address).strip(" ,")
    return address or None


def find_payment(text: str) -> str | None:
    t = text.lower()
    for word, value in (("jazzcash", "jazzcash"), ("easypaisa", "easypaisa"), ("bank", "bank transfer"),
                        ("advance", "advance"), ("cash", "cod"), ("cod", "cod")):
        if word in t:
            return value
    return None


# ---------------------------------------------------------------- the practice agent
def run(phone: str) -> dict:
    conv = db.get_conversation(phone)
    last = [m for m in conv["messages"] if m["role"] == "customer"][-1]["text"]
    state = conv.get("practice") or {"items": [], "name": None, "address": None, "when": None, "payment": None}

    # 1. A summary is waiting and the customer clearly said yes -> save the order
    if conv.get("draft_order") and tools.customer_confirmed(phone):
        r = tools.confirm_order(phone)
        if r.get("ok"):
            conv = db.get_conversation(phone)
            conv["practice"] = None
            db.save_conversation(phone, conv)
            return _say(f"Shukriya! Aap ka order {r['order_id']} confirm ho gaya. Total Rs {r['total']:,}.",
                        ["confirm_order"])
        return _say("Order save nahi ho saka, owner aap se rabta karein ge.", ["confirm_order"])

    # 2. Complaint -> tell the owner
    if COMPLAINT.search(last):
        tools.flag_owner(phone, last[:160], "complaint")
        return _say("Bohat maazrat! Main ne owner ko bata diya hai, woh jald aap se rabta karein ge.", ["flag_owner"])

    # 3. Booking
    if BOOKING.search(last) and not state["items"]:
        when = parse_when(last)
        if not when:
            return _say("Zaroor! Kis din aur kitne baje aana chahein ge?", [])
        r = tools.create_booking(phone, "Cake tasting / consultation", when, find_name(last) or "")
        if r.get("ok"):
            return _say(f"Aap ki booking {when} ke liye confirm hai. ({r['booking_id']})", ["create_booking"])
        return _say(f"Yeh time nahi mil sakta: {r.get('error')}", ["create_booking"])

    # 4. Remember new details from this message
    product = find_product(last)
    if product:
        state["items"] = [{"product_id": product["id"], "quantity": find_quantity(last)}]
    state["when"] = parse_when(last) or state["when"]
    state["name"] = find_name(last) or state["name"]
    state["address"] = find_address(last) or state["address"]
    state["payment"] = find_payment(last) or state["payment"]
    conv["practice"] = state
    db.save_conversation(phone, conv)
    used = []

    # 5. Bargaining (limits are enforced in tools.check_discount, same as the real agent)
    if BARGAIN.search(last):
        if not state["items"]:
            return _say("Kis cheez par discount chahiye? Product ka naam bata dein.", [])
        d = tools.check_discount(phone, state["items"][0]["product_id"])
        used.append("check_discount")
        offer = (f"{d['name']}: {d['discount_percent']:g}% off, ab Rs {d['new_price']:,}."
                 + (" Yeh hamari final price hai." if d["is_final_offer"] else ""))
        if not all(state[k] for k in ("name", "address", "when")):
            return _say(offer + " Order ke liye apna naam, address aur delivery ka din/time bata dein.", used)

    # 6. Nothing about an order yet
    if not state["items"]:
        return _say("Ji zaroor! Kaunsi cheez aur kitni chahiye? Menu se product ka naam likh dein.", used)

    # 7. Ask for what is missing, or build the summary card
    missing = [label for key, label in (("name", "naam"), ("address", "poora address"), ("when", "delivery ka din aur time"))
               if not state[key]]
    if missing:
        p = db.get_product(state["items"][0]["product_id"])
        return _say(f"{p['name']} Rs {p['price']:,}. Order ke liye {', '.join(missing)} bata dein.", used)

    r = tools.preview_order(phone, state["items"], state["name"], state["address"], state["when"],
                            state["payment"] or "cod")
    used.append("preview_order")
    if not r.get("ok"):
        problem = "; ".join(r.get("problems") or []) or ", ".join(r.get("missing") or [])
        if "time" in problem.lower() or "soon" in problem.lower() or "hours" in problem.lower():
            conv = db.get_conversation(phone)
            conv["practice"]["when"] = None
            db.save_conversation(phone, conv)
        return _say(f"Yeh possible nahi: {problem}. Meharbani kar ke doosra time ya address bata dein.", used)
    tip = " Ghar/block number aur koi nishani (landmark) bhi bata dein." if r.get("address_incomplete") else ""
    return _say("Order summary neeche hai. Confirm kar dein?" + tip, used, r["summary"])
