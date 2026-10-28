"""Nemotron Super tool-calling agent for orders, bookings, bargaining and complaints.

Loop: send the conversation + tool list to Nemotron Super. If it asks for tools, run them in
Python, send the results back, and ask again. Stop when it writes a normal reply (max 6 steps).
"""
import json
import math
import re
import time

import ai
import db
import tools

MAX_STEPS = 6
DEADLINE_SECONDS = 30  # stop before the server's own time limit, so the customer always gets a reply
HISTORY = 12  # how many earlier messages the model sees

# Replies that only promise to do something ("ek moment, products dhundhta hoon") instead of doing it.
STALL_WORDS = ("ek moment", "ek sec", "ek minute", "abhi dekhta", "abhi dekhti", "check karta", "check karti",
               "check kar ke", "dhundhta", "dhundhti", "nikalta", "nikalti", "product id", "product_id",
               "let me", "one moment", "please wait", "check karte", "check krte", "check karke",
               "dekhte hain", "dekh ke batat", "pata karte", "pata kar ke")
NUDGE = ("SYSTEM NOTE: do not tell the customer you will check something. Call the tool you need now "
         "(product ids are in SHOP INFO, e.g. [p1]) and then reply with the result. Never mention ids or tools.")


# Sentences where the model narrates its own work ("Let me fetch prices.", "Flag owner.", "I'll call
# confirm_order.", "Customer abhi tak ... Main unse poochta hoon"). They are removed before anything is sent.
NARRATION = re.compile(
    r"\b(let me|let's (?:check|see|fetch|call)|i'?ll (?:get|call|fetch|search|check|look|use|run|confirm the order)|"
    r"i will (?:get|call|fetch|search|check|use|run)|fetch(?:ing)?|get products|get_products|get_customer|"
    r"preview_order|preview order|confirm_order|check_discount|flag_owner|create_booking|flag(?:ged)? (?:the )?owner|tool calls?|"
    r"main unse poochta|main unse poochti|the customer (?:has|hasn't|wants|said)|customer abhi tak|"
    r"let's preview|preview with|proceeding normally|system says|need customer data|call now|check discount|ask details)\b",
    re.IGNORECASE)


def clean_reply(text: str) -> str:
    """Drop the model's narration sentences; keep everything written for the customer."""
    parts = re.split(r"(?<=[.!?\n])\s+", (text or "").strip())
    kept = [p for p in parts if p.strip() and not NARRATION.search(p)]
    return " ".join(kept).strip()


THANKS = re.compile(r"[ ,.!-]*(\b(?:shukriya|shukria|thank you|thanks|jazak\s?allah(?: khair)?)\b|شکریہ)[ .!۔]*",
                    re.IGNORECASE)


def limit_thanks(reply: str, order_saved: bool) -> str:
    """Thank the customer once, and only when an order was saved this turn."""
    matches = list(THANKS.finditer(reply or ""))
    if not matches:
        return reply
    if order_saved:  # keep the first thank-you, drop repeats
        head = reply[:matches[0].end()]
        tail = THANKS.sub(" ", reply[matches[0].end():])
        return re.sub(r" {2,}", " ", head + tail).strip()
    text = re.sub(r" {2,}", " ", THANKS.sub(" ", reply)).strip(" ,-")
    return text or reply


def is_stall(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in STALL_WORDS)


def mask(phone: str) -> str:
    return phone[:4] + "-****" + phone[-3:] if len(phone) >= 7 else "****"


def loyalty_text(r: dict) -> str:
    if not r.get("active"):
        return ""
    if r["eligible"]:
        return (f" LOYALTY: this will be their {tools.nth(r['order_number'])} order, so it gets the loyalty reward "
                f"of {r['percent']:g}% off (the system adds it to the order total). Tell them happily.")
    return (f" LOYALTY: this will be their {tools.nth(r['order_number'])} order; {r['orders_until_reward']} more "
            f"order(s) after this one until their {r['reward_percent']:g}% loyalty reward.")


def customer_info(phone: str) -> str:
    c = tools.get_customer(phone)
    if not c["returning"]:
        return "New customer (no previous orders)." + loyalty_text(tools.loyalty(phone))
    address = c["addresses"][0] if c["addresses"] else "none saved"
    text = (f"Returning customer. Saved name: {c['name']}. Saved address: {address}. "
            f"Other saved addresses: {c['addresses'][1:] or 'none'}.")
    if c["last_order"]:
        items = ", ".join(f"{i['quantity']} x {i['name']}" for i in c["last_order"]["items"])
        text += f" Last order: {items} (Rs {c['last_order']['total']:,})."
    return text + loyalty_text(c["loyalty"])


def draft_info(phone: str) -> str:
    d = db.get_conversation(phone).get("draft_order")
    if not d:
        return "None yet."
    items = ", ".join(f"{i['quantity']} x {i['name']} [{i['product_id']}] @ Rs {i['unit_price']:,}" for i in d["items"])
    return (f"Items: {items}. Name: {d['customer_name']}. Address: {d['address']}. "
            f"Delivery: {d['delivery_time']}. Payment: {d['payment_type']}. TOTAL Rs {d['total']:,} "
            "(waiting for the customer to confirm).")


def owner_messages(phone: str, limit: int = 6) -> list[str]:
    """What the owner personally wrote to this customer (after a takeover)."""
    return [m["text"] for m in db.get_conversation(phone)["messages"] if m["role"] == "owner" and m["text"]][-limit:]


OWNER_BLOCK = ("\n\nTHE OWNER ALREADY WROTE TO THIS CUSTOMER (these lines are in the chat above as shop replies). "
               "They are final: the owner personally decided them. Use them (prices, times, answers), tell the "
               "customer plainly what the owner said if it still matters, and never say the owner will confirm "
               "something the owner already answered:\n")


def build_messages(phone: str, language: str) -> list[dict]:
    shop = db.get_shop()
    now = db.now_karachi()
    from datetime import timedelta

    kal, parson = now + timedelta(days=1), now + timedelta(days=2)
    cake = tools.earliest_slot(tools.notice_hours(["cake"]))
    other = tools.earliest_slot(tools.notice_hours([]))
    dates = (f"aaj (today) = {now:%A %Y-%m-%d}; kal (tomorrow) = {kal:%A %Y-%m-%d}; "
             f"parson (day after tomorrow) = {parson:%A %Y-%m-%d}. "
             f"Earliest possible delivery right now: cakes {cake:%A %Y-%m-%d %H:%M}, "
             f"other items {other:%A %Y-%m-%d %H:%M} (calculated by the system from shop hours and notice rules).")
    system = ai.load_prompt("agent.txt").format(
        shop_name=shop["name"], city=shop.get("city", ""), now=now.strftime("%Y-%m-%d %H:%M"),
        weekday=now.strftime("%A"), draft_info=draft_info(phone), phone_masked=mask(phone),
        language_instruction=ai.LANG_INSTRUCTIONS.get(language, ai.LANG_INSTRUCTIONS["roman_urdu"]),
        customer_info=customer_info(phone), shop_info=db.shop_info_text(),
    ) + "\n\nDATES AND EARLIEST TIMES (trust these, do not calculate them yourself)\n" + dates
    said = owner_messages(phone)
    if said:
        system += OWNER_BLOCK + "\n".join(f"- {t[:300]}" for t in said)
    messages = [{"role": "system", "content": system}]
    for m in db.get_conversation(phone)["messages"][-HISTORY:]:
        if m["role"] in ("customer", "assistant", "owner") and m["text"]:
            role = "user" if m["role"] == "customer" else "assistant"
            messages.append({"role": role, "content": m["text"]})
    return messages


# ------------------------------------------------------------------ reply guards (checked in code)
# The model only writes the words. Every "Rs" amount and "%" in its reply must be one the system can
# explain (a real price, an allowed discount, the delivery fee, a total from a tool). Otherwise it is
# asked to fix the reply; if it still can't, the owner is alerted and a safe reply is sent instead.
AMOUNT = re.compile(r"(?:\brs\.?|\brupees?|rupay|rupaye|pkr|₨)\s*([\d][\d,]*)|([\d][\d,]*)\s*(?:rs\b|rupees?|rupay|rupaye|pkr)",
                    re.IGNORECASE)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|fisad)", re.IGNORECASE)
OWNER_SAID = re.compile(r"\b(owner|malik|maalik)\s*(sahab|sahib|saheb)?\s*ne\b", re.IGNORECASE)
OWNER_PROMISE = re.compile(r"\b(owner|malik|maalik)\s*(sahab|sahib|saheb)?\s*(ko|se|aap se|jald|contact|rabta)", re.IGNORECASE)
SAFE_PRICE_REPLY = "Ji, is price ke liye main owner se confirm kar ke aap ko batati hoon."
# Promises about things the shop never wrote down (diet, money back, replacement, pickup...). Discounts are
# left out here: bargaining talks about them all the time and the price guard above already checks the numbers.
AGENT_RISKY = re.compile(r"\b(eggless|egg free|sugar[- ]?free|gluten|vegan|refunds?|exchange|replace\w*|"
                         r"pickup|pick up|warranty|guarantee|free|custom|halal|organic|preservatives?)\b", re.IGNORECASE)
INTERNAL_WORDS = re.compile(r"\b(flag(?:ged|ging)?|flag_owner|tool|tools|system|shop info|product[_ ]id|preview|proceeding|"
                            r"customer data)\b", re.IGNORECASE)
NOT_IN_SHOP = "is not in the shop's info"


def _num(text: str) -> int:
    return int(text.replace(",", "")) if text.replace(",", "").isdigit() else -1


def allowed_numbers(phone: str, tool_results: list) -> tuple[set, set]:
    """(amounts, percents) the reply may use, all calculated in code."""
    shop = db.get_shop()
    conv = db.get_conversation(phone)
    reward = tools.loyalty(phone)
    fee = int(shop.get("delivery_fee", 0) or 0)
    amounts, percents = {fee}, {0, 100}  # 100: "100% fresh"
    if reward["active"]:
        percents.add(reward["reward_percent"])
    for p in db.get_products():
        mx = float(p.get("max_discount_percent", 0) or 0)
        agreed = conv["discounts"].get(p["id"], {}).get("percent", 0)
        pcts = {0, mx, math.ceil(mx / 2) if mx else 0, agreed, reward["percent"]}
        percents |= {mx, math.ceil(mx / 2) if mx else 0, agreed}
        for pct in pcts:
            unit = round(p["price"] * (1 - pct / 100))
            for q in range(1, 21):  # 1-20 boxes/cakes, with or without delivery
                amounts |= {unit * q, unit * q + fee, (p["price"] - unit) * q}
    c = db.get_customer(phone) or {}
    last = db.get_order(c["last_order_id"]) if c.get("last_order_id") else None
    if last:
        amounts |= {last.get("total", 0), last.get("subtotal", 0)}
    sources = [db.shop_info_text(), json.dumps(conv.get("draft_order") or {})] + [json.dumps(r) for r in tool_results]
    # numbers the customer gave as their budget may be repeated back ("Rs 3,000 ke budget mein...")
    sources += [m["text"] for m in conv["messages"] if m["role"] == "customer" and "budget" in m["text"].lower()]
    # prices and percents the OWNER typed to this customer are the owner's own decision: repeating them is fine
    owner_text = [m["text"] for m in conv["messages"] if m["role"] == "owner" and m["text"]]
    sources += owner_text
    for t in owner_text:
        percents |= {float(x) for x in PERCENT.findall(t)}
    for src in sources:
        amounts |= {int(n) for n in re.findall(r"\d+", src.replace(",", ""))}
    return amounts, percents


FALSE_CANCEL = re.compile(r"\b(cancell?ed|cancel (?:ho gaya|ho gya|kar diya|kardiya|kar di|kardi|ho chuka))\b|"
                          r"order cancel ho", re.IGNORECASE)
CANT_CANCEL = "you cannot cancel orders"
LIMIT_CLAIM = re.compile(r"\b(max(?:imum)?\s*limit|order limit|too big|bohat bara order|limit (?:hai|is|se zyada))\b",
                         re.IGNORECASE)
ENGLISH_WORDS = {"the", "we", "you", "i'll", "i", "let", "let's", "have", "haven't", "what", "would", "like", "your",
                 "and", "to", "is", "are", "will", "please", "can", "for", "it", "now", "just", "then", "before",
                 "need", "how", "many", "of", "each", "want", "all", "tell", "provide", "which", "do", "does",
                 "too", "big", "suggest", "fewer", "contact", "soon", "they'll", "list", "got", "with"}
ROMAN_WORDS = {"hai", "hain", "ji", "jee", "aap", "kar", "ka", "ki", "ke", "mein", "nahi", "hum", "ko", "se", "bhi",
               "kya", "dein", "chahiye", "theek", "shukriya", "batayein", "bata"}


# The order is only saved when confirm_order succeeds. Anything else that says so is a false promise.
ORDER_CLAIM = re.compile(r"\border\s+(?:save|saved|confirmed|placed|booked)\b|\b(?:save|confirm|book)\s+ho\s?(?:gaya|gya|chuka)\b|"
                         r"\border\s*#|\border number\b", re.IGNORECASE)
SMS_CLAIM = re.compile(r"\bsms\b", re.IGNORECASE)
TELEGRAPHIC = re.compile(r"(?:^|[.!?]\s+)(?:name|address|time|payment|quantity)\s*\?\s+"
                         r"(?:name|address|time|payment|quantity)\s*\?", re.IGNORECASE)
FALSE_ORDER = ("you said the order is saved or confirmed, but confirm_order did not succeed this turn - the order is "
               "NOT saved; ask for what is missing, or show the summary and ask 'Confirm kar dein?'")
NO_SMS = "there is no SMS service - never promise an SMS"
FRAGMENTS = "write complete, polite sentences instead of fragments like 'Name? Address?'"
SOFT_MARKERS = ("reply in Roman Urdu", "internal word", NO_SMS, FRAGMENTS)  # style slips: fix once, never alert the owner
NOT_SAVED_REPLY = {
    "roman_urdu": "Abhi aap ka order confirm nahi hua. Mujhe aap ka naam, poora address, delivery ka time aur payment ka tareeqa chahiye.",
    "urdu": "ابھی آپ کا آرڈر کنفرم نہیں ہوا۔ مجھے آپ کا نام، پورا پتہ، ڈیلیوری کا وقت اور ادائیگی کا طریقہ چاہیے۔",
    "english": "Your order is not confirmed yet. Please send your name, full address, delivery time and payment method.",
}


def is_soft(problem: str) -> bool:
    return any(m in problem for m in SOFT_MARKERS)


def owner_note(problems: list[str]) -> str:
    """The owner reads this in the Inbox: plain words only, never our internal checks."""
    text = "; ".join(problems)
    if NOT_IN_SHOP in text:
        return "Customer asked about something your shop info doesn't cover (for example eggless or refund). Please reply."
    if CANT_CANCEL in text:
        return "Customer wants to cancel or change an order. Please handle it in Orders."
    if "Rs " in text or "%" in text:
        return "Customer asked about a price or discount the assistant could not confirm. Please reply."
    return "The assistant was not sure how to reply to this customer. Please check the chat."


def tidy(reply: str) -> str:
    """Last resort for style slips: drop the sentences that carry internal words or an SMS promise."""
    parts = re.split(r"(?<=[.!?\n])\s+", (reply or "").strip())
    kept = [p for p in parts if p.strip() and not INTERNAL_WORDS.search(p) and not SMS_CLAIM.search(p)]
    return " ".join(kept).strip()


CLOCK = re.compile(r"(?<![\d:])(\d{1,2})(?::(\d{2}))?\s*(baje|baja|bje|bajay|am|pm)\b", re.IGNORECASE)


def clock_time(text: str) -> str | None:
    """'aj raat 11 baja' -> '23:00'. Only when the day-part (raat/shaam/...) or am/pm makes it clear."""
    t = (text or "").lower()
    m = CLOCK.search(t)
    if not m:
        return None
    h, mi, unit = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if h > 24 or mi > 59:
        return None
    if unit == "pm":
        h = h + 12 if h < 12 else h
    elif unit == "am":
        h = 0 if h == 12 else h
    elif re.search(r"\b(raat|rat|night)\b", t):
        h = h + 12 if 6 <= h <= 11 else (0 if h == 12 else h)
    elif re.search(r"\b(shaam|sham|evening)\b", t):
        h = h + 12 if h < 12 else h
    elif re.search(r"\b(dopahar|dopehar|dupaar|dupahar|afternoon)\b", t):
        h = h + 12 if 1 <= h <= 6 else h
    elif re.search(r"\b(subah|subha|morning)\b", t):
        pass
    else:
        return None
    return f"{h % 24:02d}:{mi:02d}"


def out_of_hours(phone: str) -> tuple[str, str, str] | None:
    """If the customer's last message names a clock time outside every shop-open window: (time, open, close)."""
    msgs = [m for m in db.get_conversation(phone)["messages"] if m["role"] == "customer"]
    when = clock_time(msgs[-1]["text"]) if msgs else None
    hours = db.get_shop().get("opening_hours") or {}
    windows = [v for v in hours.values() if v]
    if not when or not windows:
        return None
    if any(o <= when <= c for o, c in windows):
        return None
    return when, windows[0][0], windows[0][1]


def sounds_english(text: str) -> bool:
    words = re.findall(r"[a-z']+", (text or "").lower())
    en = sum(w in ENGLISH_WORDS for w in words)
    ur = sum(w in ROMAN_WORDS for w in words)
    return en >= 3 and en > 2 * ur


def reply_problems(phone: str, reply: str, used: list, tool_results: list, language: str = "") -> list[str]:
    amounts, percents = allowed_numbers(phone, tool_results)
    problems = []
    for a, b in AMOUNT.findall(reply or ""):
        n = _num(a or b)
        if n >= 0 and n not in amounts:
            problems.append(f"Rs {n:,} is not a price the system allows")
    for pct in PERCENT.findall(reply or ""):
        if float(pct) not in percents:
            problems.append(f"{pct}% is not a discount the owner allows")
    owner_spoke = any(m["role"] == "owner" for m in db.get_conversation(phone)["messages"])
    if OWNER_SAID.search(reply or "") and not owner_spoke:
        problems.append("the owner did not say anything in this chat - never put words in the owner's mouth")
    shop = ai._norm(db.shop_info_text())
    for word in AGENT_RISKY.findall(reply or ""):
        if ai._norm(word)[:5] not in shop:
            problems.append(f"'{word}' {NOT_IN_SHOP} - never promise or describe it; say the owner will confirm "
                            "and call flag_owner")
    if LIMIT_CLAIM.search(reply or ""):
        problems.append("there is no order limit - accept any quantity; the owner is alerted about big orders "
                        "automatically")
    if FALSE_CANCEL.search(reply or ""):
        problems.append(f"{CANT_CANCEL} - only the owner can; say the owner will handle it and call flag_owner")
    if language in ("roman_urdu", "urdu") and sounds_english(reply):
        problems.append("the customer writes Roman Urdu: reply in Roman Urdu, not English")
    if INTERNAL_WORDS.search(reply or ""):
        problems.append("you used an internal word (flag, tool, system) with the customer - say it in normal words")
    statements = [x for x in re.split(r"(?<=[.!?\n])", reply or "") if not x.strip().endswith("?")]
    saved_now = any(r.get("ok") and r.get("order_id") for r in tool_results)
    if not saved_now and any(ORDER_CLAIM.search(x) for x in statements):
        problems.append(FALSE_ORDER)
    if SMS_CLAIM.search(reply or ""):
        problems.append(NO_SMS)
    if TELEGRAPHIC.search(reply or ""):
        problems.append(FRAGMENTS)
    if any(OWNER_PROMISE.search(x) for x in statements) and "flag_owner" not in used:
        problems.append("you told the customer about the owner but did not call flag_owner")
    return problems


def guard_note(problems: list[str]) -> str:
    return ("SYSTEM NOTE: your last reply was not sent because " + "; ".join(problems) + ". "
            "Rewrite it using ONLY prices, discounts and totals returned by tools (call check_discount or "
            "preview_order if you need a new number). If the owner really needs to know, call flag_owner first. "
            "Do not mention this note.")


# A customer asking for a lower price, even with typos ("ptice kam?") or when Nano labels it something else.
BARGAIN_WORDS = re.compile(r"\b(kam|kum|discount|disc|sasta|sasti|less|cheaper|last price|best price|rate kam|"
                           r"rs \d+ (?:mein|me|main)|\d+ (?:mein|me|main) de)\b|کم|رعایت", re.IGNORECASE)


def asked_for_discount(phone: str) -> bool:
    msgs = [m for m in db.get_conversation(phone)["messages"] if m["role"] == "customer"]
    return bool(msgs) and bool(BARGAIN_WORDS.search(msgs[-1]["text"]))


DISCOUNT_NUDGE = ("SYSTEM NOTE: the customer asked for a lower price. Call check_discount now for the product "
                  "they are buying (see ORDER IN PROGRESS or the chat) and offer exactly what it returns.")


CLOSED_WORDS = ("nahi", "not possible", "closed", "band", "outside", "possible nahi", "mumkin")
TIME_NUDGE = ("SYSTEM NOTE: the customer asked for {t}, which is outside shop hours ({o}-{c}). Tell them politely "
              "that time is not possible and offer a time inside shop hours. Do not accept this time.")


# ---- last polish on every customer reply (code, not the AI) ----
MALE_VERB = re.compile(r"\b(\w{2,}?)ta (hoon|hun)\b", re.IGNORECASE)
MALE_FUTURE = re.compile(r"\b(\w+?)(unga|oonga)\b", re.IGNORECASE)
MALE_GAYA = re.compile(r"\b(main|mein) (samajh|aa|ja|ho) gaya\b", re.IGNORECASE)
ISO_TIME = re.compile(r"\b(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})\b")
FALSE_ACTION = re.compile(
    r"\b(menu|price|prices|settings?|stock)\b.{0,25}\b(restore|restored|update|updated|change|changed|reset|delete|deleted)\b"
    r".{0,15}\b(ho gaya|ho gayi|kar diya|kar di|done|ho chuka)\b|"
    r"\b(restore|restored|reset)\b.{0,20}\b(ho gaya|ho gayi|kar diya|kar di|done)\b", re.IGNORECASE)
CANT_CHANGE = {"roman_urdu": "Ji, menu aur settings sirf owner badal sakte hain. Main aap ko abhi ka menu bata sakti hoon.",
               "urdu": "جی، مینو اور سیٹنگز صرف اونر بدل سکتے ہیں۔ میں آپ کو ابھی کا مینو بتا سکتی ہوں۔",
               "english": "Only the owner can change the menu or settings. I can tell you the current menu."}


def _fem(m):  # "karta hoon" -> "karti hoon": the shop assistant always speaks as a woman
    return f"{m.group(1)}ti {m.group(2)}"


def _human_time(m):
    from datetime import datetime
    try:
        d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
        return f"{d.day} {d:%b}, {d.hour % 12 or 12}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"
    except ValueError:
        return m.group(0)


def polish_reply(reply: str, language: str) -> str:
    """Final touch: one voice (woman), readable dates, and no claim of changing the shop's menu or settings."""
    if not reply:
        return reply
    if FALSE_ACTION.search(reply):
        return CANT_CHANGE.get(language, CANT_CHANGE["roman_urdu"])
    reply = ISO_TIME.sub(_human_time, reply)
    if language != "english":
        reply = MALE_VERB.sub(_fem, reply)
        reply = MALE_FUTURE.sub(lambda m: m.group(1) + ("ungi" if m.group(2).lower() == "unga" else "oongi"), reply)
        reply = MALE_GAYA.sub(lambda m: f"{m.group(1)} {m.group(2)} gayi", reply)
    return reply


def with_order_number(reply: str, results: list, language: str) -> str:
    """A saved order always shows its real number, never a placeholder or a promise of an SMS."""
    done = next((r for r in results if r.get("ok") and r.get("order_id")), None)
    if done and str(done["order_id"]) not in (reply or ""):
        line = (f"Your order number is {done['order_id']}." if language == "english"
                else f"Aap ka order number {done['order_id']} hai.")
        reply = f"{(reply or '').rstrip()} {line}".strip()
    return reply


def run_agent(phone: str, language: str, intent: str = "") -> dict:
    """Returns {"reply": str, "tools_used": [...], "order_summary": dict|None}."""
    if ai.MOCK:  # no API key: rule-based practice agent that uses the same tools (see practice.py)
        import practice

        return practice.run(phone)

    messages = build_messages(phone, language)
    used, summary, nudged, discount_nudged, guarded, time_nudged = [], None, 0, False, False, False
    results = []  # every tool result this turn: numbers in them are allowed in the reply
    start = time.monotonic()
    for _ in range(MAX_STEPS):
        if time.monotonic() - start > DEADLINE_SECONDS:
            break  # too slow today: alert the owner below instead of letting the request time out
        msg = ai.chat_with_tools(ai.SUPER, messages, tools.TOOLS)
        if not msg.tool_calls:
            raw = ai.strip_thinking(msg.content or "")
            reply = clean_reply(raw)
            if (not reply or is_stall(reply)) and nudged < 2:  # it only narrated or promised: make it act
                nudged += 1
                reply = raw
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": NUDGE})
                continue
            if (asked_for_discount(phone) and "check_discount" not in used
                    and not discount_nudged):
                # bargaining must always go through the owner's limits in code, never the model's own answer
                discount_nudged = True
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": DISCOUNT_NUDGE})
                continue
            late = out_of_hours(phone)
            if (late and not time_nudged and not any(w in reply.lower() for w in CLOSED_WORDS)):
                # a clock time outside shop hours is refused in code, even before the order is complete
                time_nudged = True
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": TIME_NUDGE.format(t=late[0], o=late[1], c=late[2])})
                continue
            if not reply:
                break  # still only narration: alert the owner below instead of sending it
            problems = reply_problems(phone, reply, used, results, language)
            if problems and not guarded:  # made-up price, false promise or style slip: ask it to fix the reply, once
                guarded = True
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": guard_note(problems)})
                continue
            if problems:
                hard = [p for p in problems if not is_soft(p)]
                if not hard:  # only a style slip: send a cleaned reply, the owner doesn't need an alert
                    reply = tidy(reply)
                    if not reply:
                        tools.flag_owner(phone, owner_note(problems), "question")
                        used.append("flag_owner")
                        reply = ai.OWNER_WILL_CONFIRM.get(language, ai.OWNER_WILL_CONFIRM["roman_urdu"])
                elif FALSE_ORDER in hard and len(hard) == 1:  # it claimed a saved order that does not exist
                    reply = NOT_SAVED_REPLY.get(language, NOT_SAVED_REPLY["roman_urdu"])
                else:  # still wrong: never send a made-up price; alert the owner so the promise is true
                    tools.flag_owner(phone, owner_note(hard), "question")
                    used.append("flag_owner")
                    if any(NOT_IN_SHOP in p or CANT_CANCEL in p for p in hard):  # never sent
                        reply = ai.OWNER_WILL_CONFIRM.get(language, ai.OWNER_WILL_CONFIRM["roman_urdu"])
                    elif FALSE_ORDER in hard:
                        reply = NOT_SAVED_REPLY.get(language, NOT_SAVED_REPLY["roman_urdu"])
                    elif any("Rs " in p or "%" in p for p in hard):
                        reply = SAFE_PRICE_REPLY
            return {"reply": with_order_number(reply, results, language), "tools_used": used, "order_summary": summary}

        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run_tool(tc.function.name, args, phone)
            used.append(tc.function.name)
            results.append(result)
            if tc.function.name == "preview_order" and result.get("ok"):
                summary = result["summary"]  # the frontend shows this as the order card
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    tools.flag_owner(phone, "The assistant took too long on this chat. Please check it.", "urgent")
    return {"reply": "Ji, main owner se confirm kar ke abhi batati hoon.", "tools_used": used,
            "order_summary": summary}
