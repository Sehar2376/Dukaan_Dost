"""Nemotron Super tool-calling agent for orders, bookings, bargaining and complaints.

Loop: send the conversation + tool list to Nemotron Super. If it asks for tools, run them in
Python, send the results back, and ask again. Stop when it writes a normal reply (max 6 steps).
"""
import json

import ai
import db
import tools

MAX_STEPS = 6
HISTORY = 12  # how many earlier messages the model sees

# Replies that only promise to do something ("ek moment, products dhundhta hoon") instead of doing it.
STALL_WORDS = ("ek moment", "ek sec", "ek minute", "abhi dekhta", "abhi dekhti", "check karta", "check karti",
               "check kar ke", "dhundhta", "dhundhti", "nikalta", "nikalti", "product id", "product_id",
               "let me check", "one moment", "please wait")
NUDGE = ("SYSTEM NOTE: do not tell the customer you will check something. Call the tool you need now "
         "(product ids are in SHOP INFO, e.g. [p1]) and then reply with the result. Never mention ids or tools.")


def is_stall(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in STALL_WORDS)


def mask(phone: str) -> str:
    return phone[:4] + "-****" + phone[-3:] if len(phone) >= 7 else "****"


def customer_info(phone: str) -> str:
    c = tools.get_customer(phone)
    if not c["returning"]:
        return "New customer (no previous orders)."
    text = f"Returning customer: {c['name']}. Saved addresses: {c['addresses']}."
    if c["last_order"]:
        items = ", ".join(f"{i['quantity']} x {i['name']}" for i in c["last_order"]["items"])
        text += f" Last order: {items} (Rs {c['last_order']['total']:,})."
    return text


def draft_info(phone: str) -> str:
    d = db.get_conversation(phone).get("draft_order")
    if not d:
        return "None yet."
    items = ", ".join(f"{i['quantity']} x {i['name']} [{i['product_id']}] @ Rs {i['unit_price']:,}" for i in d["items"])
    return (f"Items: {items}. Name: {d['customer_name']}. Address: {d['address']}. "
            f"Delivery: {d['delivery_time']}. Payment: {d['payment_type']}. TOTAL Rs {d['total']:,} "
            "(waiting for the customer to confirm).")


def build_messages(phone: str, language: str) -> list[dict]:
    shop = db.get_shop()
    now = db.now_karachi()
    system = ai.load_prompt("agent.txt").format(
        shop_name=shop["name"], city=shop.get("city", ""), now=now.strftime("%Y-%m-%d %H:%M"),
        weekday=now.strftime("%A"), draft_info=draft_info(phone), phone_masked=mask(phone),
        language_instruction=ai.LANG_INSTRUCTIONS.get(language, ai.LANG_INSTRUCTIONS["roman_urdu"]),
        customer_info=customer_info(phone), shop_info=db.shop_info_text(),
    )
    messages = [{"role": "system", "content": system}]
    for m in db.get_conversation(phone)["messages"][-HISTORY:]:
        if m["role"] in ("customer", "assistant", "owner") and m["text"]:
            role = "user" if m["role"] == "customer" else "assistant"
            messages.append({"role": role, "content": m["text"]})
    return messages


def run_agent(phone: str, language: str) -> dict:
    """Returns {"reply": str, "tools_used": [...], "order_summary": dict|None}."""
    if ai.MOCK:  # no API key: rule-based practice agent that uses the same tools (see practice.py)
        import practice

        return practice.run(phone)

    messages = build_messages(phone, language)
    used, summary, nudged = [], None, False
    for _ in range(MAX_STEPS):
        msg = ai.chat_with_tools(ai.SUPER, messages, tools.TOOLS)
        if not msg.tool_calls:
            reply = ai.strip_thinking(msg.content or "")
            if is_stall(reply) and not nudged:  # it only promised to check: make it actually do it, once
                nudged = True
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": NUDGE})
                continue
            return {"reply": reply, "tools_used": used, "order_summary": summary}

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
            if tc.function.name == "preview_order" and result.get("ok"):
                summary = result["summary"]  # the frontend shows this as the order card
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    tools.flag_owner(phone, "Assistant could not finish this conversation", "urgent")
    return {"reply": "Ji, main owner se confirm kar ke abhi batati hoon.", "tools_used": used,
            "order_summary": summary}
