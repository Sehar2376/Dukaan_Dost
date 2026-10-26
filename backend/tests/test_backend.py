"""Tests for tools, agent loop, summaries, setup and webhook. No API key needed:  pytest -q"""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["MOCK_AI"] = "1"
os.environ["FIREBASE_CREDENTIALS"] = ""
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import ai  # noqa: E402
import db  # noqa: E402
import tools  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)
GOOD = "House 12, Street 5, Block 13-D, near Masjid, Gulshan-e-Iqbal"


def future(days: int = 2, hm: str = "18:00") -> str:
    """A valid delivery time: N days from now (Karachi), inside shop hours."""
    from datetime import timedelta
    return f"{(db.now_karachi() + timedelta(days=days)).date().isoformat()} {hm}"


def say(phone: str, text: str) -> None:
    db.add_message(phone, "customer", text)


@pytest.fixture(autouse=True)
def fresh_db():
    db.store.data.clear()
    db.load_sample_shop(force=True)


# ------------------------------------------------------------------ bargaining (F4)
def test_discount_steps_and_never_exceeds_max():
    phone = "03000000001"
    first = tools.check_discount(phone, "p2", 50)        # max is 10%
    second = tools.check_discount(phone, "p2", 90)
    third = tools.check_discount(phone, "p2", 90)
    assert first["discount_percent"] == 5 and not first["is_final_offer"]
    assert second["discount_percent"] == 10 and second["is_final_offer"]
    assert third["discount_percent"] == 10 and "owner" in third["note"]


def test_order_uses_only_agreed_discount():
    phone = "03000000002"
    tools.check_discount(phone, "p2")  # agreed 5%
    r = tools.preview_order(phone, [{"product_id": "p2", "quantity": 1}], "Ayesha", GOOD, future())
    assert r["ok"]
    s = r["summary"]
    assert s["subtotal"] == 4400 and s["discount"] == 220 and s["total"] == 4400 - 220 + 200


def test_preview_asks_for_missing_details_and_rejects_out_of_stock():
    r = tools.preview_order("03000000003", [{"product_id": "p5", "quantity": 1}], "", "", "")
    assert not r["ok"] and "customer_name" in r["missing"] and any("out of stock" in p for p in r["problems"])


def test_outside_delivery_area():
    r = tools.preview_order("03000000004", [{"product_id": "p1", "quantity": 1}], "Ali", "House 3, Lahore", future())
    assert not r["ok"] and "outside" in r["problems"][0]


# ------------------------------------------------------------------ confirm + risk + memory (F3, F7)
def test_confirm_saves_order_scores_risk_and_remembers_customer():
    phone = "03000000005"
    tools.preview_order(phone, [{"product_id": "p2", "quantity": 3}], "Bilal", "Gulshan", future(), "cod")
    say(phone, "Haan confirm kar dein")
    r = tools.confirm_order(phone)
    assert r["ok"]
    order = db.get_order(r["order_id"])
    assert order["risk_level"] == "high" and order["profit"] == 3 * (4400 - 2750)
    assert {f["type"] for f in db.list_flags()} == {"high_risk", "large_order"}
    c = tools.get_customer(phone)
    assert c["returning"] and c["name"] == "Bilal" and c["last_order"]["total"] == r["total"]


def test_confirm_without_preview_fails():
    assert not tools.confirm_order("03000000006")["ok"]


# ------------------------------------------------------------------ agent loop with a fake Nemotron
def _call(name, args, i):
    return NS(id=f"c{i}", function=NS(name=name, arguments=json.dumps(args)))


def test_agent_loop_runs_tools_then_replies(monkeypatch):
    script = [
        NS(content="", tool_calls=[_call("preview_order", {"items": [{"product_id": "p1", "quantity": 1}],
                                                            "customer_name": "Sana", "address": GOOD,
                                                            "delivery_time": future()}, 1)]),
        NS(content="Summary: Rs 2,400. Confirm kar dein?", tool_calls=None),
    ]
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda model, messages, tl: script.pop(0))
    db.add_message("03000000007", "customer", "1kg chocolate cake chahiye")
    out = agent.run_agent("03000000007", "roman_urdu")
    assert out["reply"].startswith("Summary") and out["tools_used"] == ["preview_order"]
    assert out["order_summary"]["total"] == 2400


def test_agent_gives_up_after_max_steps(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools",
                        lambda m, msgs, tl: NS(content="", tool_calls=[_call("get_products", {}, 1)]))
    out = agent.run_agent("03000000008", "roman_urdu")
    assert len(out["tools_used"]) == agent.MAX_STEPS and db.list_flags()


# ------------------------------------------------------------------ endpoints
def test_chat_complaint_creates_flag():
    r = client.post("/chat", json={"phone": "03000000009", "message": "Order late hai, worst service!"})
    assert r.json()["intent"] == "complaint" and r.json()["needs_owner"]
    assert client.get("/flags").json()[0]["type"] == "complaint"


def test_takeover_and_owner_reply():
    client.post("/conversations/03000000010/takeover", params={"paused": True})
    assert client.post("/chat", json={"phone": "03000000010", "message": "hello"}).json()["ai_paused"]
    client.post("/conversations/03000000010/reply", json={"text": "Ji main owner bol rahi hoon"})
    msgs = client.get("/conversations/03000000010").json()["messages"]
    assert msgs[-1]["role"] == "owner"


def test_order_status_updates_customer_counts():
    tools.preview_order("03000000011", [{"product_id": "p1", "quantity": 1}], "Hina", GOOD, future())
    say("03000000011", "ji confirm")
    oid = tools.confirm_order("03000000011")["order_id"]
    client.patch(f"/orders/{oid}", json={"status": "cancelled"})
    assert db.get_customer("03000000011")["cancelled_orders"] == 1


def test_setup_parse_and_save():
    parsed = client.post("/setup/parse", json={"text": "cake 2200"}).json()
    assert parsed["warnings"]  # mock has no cost price -> warning
    r = client.post("/setup/save", json={"shop": parsed["shop"], "products": parsed["products"], "faqs": []})
    assert r.json()["ok"] and client.get("/setup").json()["products"][0]["name"] == "Chocolate cake 1kg"


def test_summaries_with_sample_data():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sample_data"))
    import load_sample
    load_sample.main(days=60)
    month = client.get("/summary/monthly").json()
    assert month["orders"] > 0 and month["profit"] > 0 and len(month["daily_chart"]) >= 28
    orders = db.list_orders()
    done = [o for o in orders if o["status"] != "cancelled" and o["created_at"][:7] == month["month"]]
    assert month["sales"] == sum(o["total"] - o["delivery_fee"] for o in done)  # hand check
    assert client.get("/summary/daily").json()["date"]


def test_whatsapp_webhook_returns_twiml():
    r = client.post("/webhook/whatsapp", data={"From": "whatsapp:+923001234567", "Body": "Timings kya hain?"})
    assert r.status_code == 200 and "<Message>" in r.text


def test_rate_limit_per_phone(monkeypatch):
    import main
    monkeypatch.setattr(main, "DAILY_LIMIT", 2)
    for _ in range(2):
        client.post("/chat", json={"phone": "03000000012", "message": "hi"})
    r = client.post("/chat", json={"phone": "03000000012", "message": "hi"})
    assert "limit" in r.json()["reply"]


# ------------------------------------------------------------------ edge-case fixes
def test_total_daily_cap_blocks_new_numbers(monkeypatch):
    import main
    monkeypatch.setattr(main, "TOTAL_DAILY_LIMIT", 3)
    for i in range(3):
        client.post("/chat", json={"phone": f"0311000000{i}", "message": "hi"})
    r = client.post("/chat", json={"phone": "03119999999", "message": "hi"}).json()  # brand-new number
    assert "zyada" in r["reply"] and r["needs_owner"]
    assert any("limit" in f["reason"] for f in db.list_flags())
    assert client.get("/usage").json()["messages"] == 4


def test_budget_guard_stops_ai(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "DAILY_BUDGET_USD", 0.01)
    db.add_usage({"cost_usd": 0.02})
    called = []
    monkeypatch.setattr(ai, "classify", lambda m: called.append(m))
    r = client.post("/chat", json={"phone": "03120000000", "message": "cake chahiye"}).json()
    assert "zyada" in r["reply"] and not called  # no AI call was made


def test_usage_records_tokens_and_cost():
    resp = NS(usage=NS(prompt_tokens=1_000_000, completion_tokens=0))
    ai.record_usage(ai.SUPER, resp)
    assert round(db.get_usage()["cost_usd"], 2) == 0.30 and db.get_usage()["super_calls"] == 1


def test_confirm_needs_a_real_yes():
    phone = "03130000000"
    tools.preview_order(phone, [{"product_id": "p1", "quantity": 1}], "Zoya", GOOD, future())
    for text in ["1kg cake chahiye", "haan lekin time 7 baje kar dein", "nahi abhi ruko"]:
        say(phone, text)
        assert not tools.confirm_order(phone)["ok"]
    say(phone, "Ji bilkul, confirm")
    assert tools.confirm_order(phone)["ok"]


def test_time_rules_in_code(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    fixed = datetime(2026, 10, 20, 12, 0, tzinfo=ZoneInfo("Asia/Karachi"))  # Tuesday noon
    monkeypatch.setattr(db, "now_karachi", lambda: fixed)
    when, problem = tools.check_time("2026-10-20 15:00", ["cake"])  # cakes need 24 h
    assert when is None and "24" in problem
    assert tools.check_time("2026-10-20 15:00", ["cookies"])[0] == "2026-10-20 15:00"  # 2 h is enough
    when, problem = tools.check_time("2026-10-23 12:00")  # Friday noon: opens at 3 pm
    assert when is None and "fri" in problem
    when, problem = tools.check_time(future(hm="03:00"))  # 3 am: shop closed
    assert when is None and "outside shop hours" in problem
    when, problem = tools.check_time("kal shaam")  # not converted
    assert when is None and "YYYY-MM-DD" in problem
    assert tools.check_time(future())[0] == future()
    r = tools.create_booking("03140000000", "Cake tasting", future(hm="23:30"))
    assert not r["ok"]


def test_agent_sees_saved_draft():
    phone = "03150000000"
    tools.preview_order(phone, [{"product_id": "p3", "quantity": 2}], "Iqra", GOOD, future())
    msgs = agent.build_messages(phone, "roman_urdu")
    assert "Red Velvet" in msgs[0]["content"] and "Iqra" in msgs[0]["content"]


def test_abuse_is_flagged_without_agent():
    r = client.post("/chat", json={"phone": "03160000000", "message": "tum log bakwas ho idiot"}).json()
    assert r["intent"] == "abuse" and r["needs_owner"]
    assert db.list_flags()[0]["type"] == "abuse"


def test_parallel_messages_same_phone_are_not_lost():
    import threading
    phone = "03170000000"
    threads = [threading.Thread(target=lambda i=i: client.post("/chat", json={"phone": phone, "message": f"msg {i}"}))
               for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    customer_msgs = [m for m in db.get_conversation(phone)["messages"] if m["role"] == "customer"]
    assert len(customer_msgs) == 8


def test_whatsapp_rejects_fake_signature(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    r = client.post("/webhook/whatsapp", data={"From": "whatsapp:+923001234567", "Body": "hi"},
                    headers={"X-Twilio-Signature": "fake"})
    assert r.status_code == 403


def test_whatsapp_valid_signature_replies_in_background(monkeypatch):
    from twilio.request_validator import RequestValidator
    import main
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.onrender.com")
    sent = []
    monkeypatch.setattr(main, "send_whatsapp", lambda phone, text: sent.append((phone, text)) or True)
    params = {"From": "whatsapp:+923001234567", "Body": "Timings kya hain?", "NumMedia": "0"}
    sig = RequestValidator("secret").compute_signature("https://example.onrender.com/webhook/whatsapp", params)
    r = client.post("/webhook/whatsapp", data=params, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200 and sent and sent[0][0] == "+923001234567"


# ------------------------------------------------------------------ Nemotron Ultra business advice
def _load_demo(days=60):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sample_data"))
    import load_sample
    load_sample.main(days=days)


def test_insights_numbers_match_orders():
    import summary
    _load_demo()
    month = db.now_karachi().strftime("%Y-%m")
    r = summary.insights(month)
    done = [o for o in db.list_orders() if o["status"] != "cancelled" and o["created_at"][:7] == month]
    assert r["totals"]["sales"] == sum(o["total"] - o["delivery_fee"] for o in done)
    assert sum(p["quantity"] for p in r["products"].values()) == sum(i["quantity"] for o in done for i in o["items"])
    assert sum(w["orders"] for w in r["weekdays"].values()) == len(done)
    assert r["month_not_finished"] is True and r["totals"]["sales_change_percent_vs_last_month"] is None
    assert r["demo_data"] is True


ADVICE = '{"headline": "Good month", "tips": [{"title": "Push brownies", "detail": "Highest margin.", "based_on": "products"}]}'


def test_advice_uses_ultra_and_is_cached(monkeypatch):
    import main
    _load_demo()
    calls = []

    def fake_chat(model, system, user, **kw):
        calls.append((model, kw.get("thinking")))
        return "<think>numbers...</think>" + ADVICE
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat", fake_chat)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    r1 = client.get("/advice/monthly").json()
    assert r1["model_used"] == ai.ULTRA and r1["tips"][0]["title"] == "Push brownies" and not r1["cached"]
    assert calls == [(ai.ULTRA, True)]  # Ultra, with reasoning on
    r2 = client.get("/advice/monthly").json()
    assert r2["cached"] and len(calls) == 1  # second visit is free
    client.get("/advice/monthly", params={"refresh": True})
    assert len(calls) == 2


def test_advice_falls_back_to_other_region_then_super(monkeypatch):
    _load_demo()
    tried = []

    def fake_chat(model, system, user, base_url=None, **kw):
        tried.append((model, base_url))
        if model == ai.ULTRA:
            raise RuntimeError("model not found")
        return ADVICE
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat", fake_chat)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    r = client.get("/advice/monthly").json()
    assert tried == [(ai.ULTRA, None), (ai.ULTRA, ai.ULTRA_BASE_URL), (ai.SUPER, None)]
    assert r["model_used"] == ai.SUPER


def test_advice_respects_budget(monkeypatch):
    _load_demo()
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "over_budget", lambda: True)
    assert client.get("/advice/monthly").status_code == 429


def test_advice_rejects_empty_tips(monkeypatch):
    with pytest.raises(ValueError):
        ai._clean_advice({"headline": "x", "tips": []})


# ------------------------------------------------------------------ dates and time zones
def test_late_night_order_counts_for_karachi_day():
    import summary
    db.save_order({"customer_phone": "03180000000", "items": [], "subtotal": 1000, "discount": 0, "delivery_fee": 200,
                   "total": 1200, "profit": 400, "status": "new", "created_at": "2026-10-20T20:30:00+00:00"})
    assert db.local_date("2026-10-20T20:30:00+00:00") == "2026-10-21"  # 1:30 am in Karachi
    assert summary.daily("2026-10-21")["orders"] == 1 and summary.daily("2026-10-20")["orders"] == 0


def test_works_without_timezone_data(monkeypatch):
    import zoneinfo

    def missing(key):
        raise zoneinfo.ZoneInfoNotFoundError(key)
    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    now = db.now_karachi()
    assert now.utcoffset().total_seconds() == 5 * 3600


def test_load_demo_endpoint_fills_running_server():
    r = client.post("/admin/load-demo", params={"days": 30}).json()
    assert r["ok"] and r["orders"] > 50 and r["customers"] == 20
    assert len(client.get("/orders").json()) == r["orders"]
    assert client.post("/admin/load-demo", params={"days": 500}).status_code == 422


def test_stall_reply_gets_one_retry(monkeypatch):
    """If Super only says 'ek moment, check karta hoon', the agent is asked once more to actually do it."""
    import agent
    from types import SimpleNamespace as NS

    replies = [NS(tool_calls=None, content="Ek moment! Products dhundhta hoon."),
               NS(tool_calls=None, content="Chocolate Fudge Cake 1kg Rs 2,200 hai.")]
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda model, messages, tl: replies.pop(0))
    out = agent.run_agent("03009990001", "roman_urdu")
    assert out["reply"].startswith("Chocolate Fudge Cake") and not replies


def test_short_answer_mid_order_goes_back_to_agent():
    """'Sham 7 baje' right after the agent asked a question is routed to the agent even if Nano says greeting."""
    import main
    conv = {"agent_at": db.now_iso()}
    assert main._mid_order(conv, "greeting") is True
    assert main._mid_order(conv, "abuse") is False
    assert main._mid_order({}, "other") is False


def test_faq_gets_recent_chat(monkeypatch):
    """Follow-ups like 'kya?' reach Nano together with the last few chat lines."""
    import main
    seen = {}

    def fake_faq(message, language, shop_info, name, city, history=""):
        seen["history"] = history
        return "Ji, aap ne 1kg chocolate cake ka poocha tha."

    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    monkeypatch.setattr(ai, "answer_faq", fake_faq)
    phone = "03009990002"
    db.add_message(phone, "customer", "1kg chocolate cake kitne ka hai?")
    db.add_message(phone, "assistant", "Rs 2,200 hai ji.")
    out = main.handle_message(phone, "kya?")
    assert "chocolate cake" in seen["history"] and "kya?" not in seen["history"]
    assert out.needs_owner is False


def test_bargain_without_check_discount_is_nudged(monkeypatch):
    """If Super refuses a discount without calling check_discount, it is asked to call it."""
    seen = []

    def fake(model, messages, tl):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return NS(tool_calls=None, content="Discount nahi mil sakta.")
        if len(seen) == 2:
            return NS(tool_calls=[_call("check_discount", {"product_id": "p1"}, 1)], content="")
        return NS(tool_calls=None, content="Aap ke liye 5% kam: Rs 2,090.")

    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", fake)
    out = agent.run_agent("03009990003", "roman_urdu", "bargain")
    assert "check_discount" in out["tools_used"] and out["reply"].startswith("Aap ke liye")
    assert "check_discount now" in seen[1]


def test_earliest_slot_respects_notice_and_hours(monkeypatch):
    """Sunday 22:30 + 24 h cake notice = Monday 22:30, after closing, so the earliest is Tuesday 10:00."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import tools
    db.load_sample_shop(force=True)
    sunday_night = datetime(2026, 10, 25, 22, 30, tzinfo=ZoneInfo("Asia/Karachi"))
    monkeypatch.setattr(db, "now_karachi", lambda: sunday_night)
    slot = tools.earliest_slot(tools.notice_hours(["cake"]))
    assert slot.strftime("%a %H:%M") == "Tue 10:00"
    ok, problem = tools.check_time("2026-10-27 18:00", ["cake"])   # "parson shaam 6 baje"
    assert ok == "2026-10-27 18:00" and problem is None
    ok, problem = tools.check_time("2026-10-26 18:00", ["cake"])   # "kal shaam 6 baje": too soon
    assert ok is None and "Tuesday 2026-10-27 10:00" in problem


def test_agent_prompt_lists_dates_and_earliest_times():
    import agent
    db.load_sample_shop(force=True)
    system = agent.build_messages("03009990004", "roman_urdu")[0]["content"]
    assert "parson (day after tomorrow)" in system and "Earliest possible delivery right now: cakes" in system


# ------------------------------------------------------------------ reply guards, confirm routing, loyalty
def test_made_up_price_is_never_sent(monkeypatch):
    """The cupcake bug: Super offered Rs 1,000 (beyond the 10% limit) and said 'owner ne bola'."""
    seen = []
    bad = "Owner ne bola: Cupcakes Rs 1,000 + delivery Rs 200 = Rs 1,200. Final offer."

    def fake(model, messages, tl):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return NS(tool_calls=None, content=bad)
        return NS(tool_calls=None, content="Maafi, Cupcakes ka best price Rs 1,080 hai (10% off).")

    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", fake)
    phone = "03009990010"
    tools.check_discount(phone, "p8")
    tools.check_discount(phone, "p8")  # 10% agreed -> Rs 1,080
    out = agent.run_agent(phone, "roman_urdu")
    assert out["reply"].endswith("(10% off).")
    assert "Rs 1,000 is not a price" in seen[1] and "owner did not say" in seen[1]


def test_still_wrong_price_sends_safe_reply_and_alerts_owner(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(tool_calls=None, content="Chalo Rs 777 final!"))
    out = agent.run_agent("03009990011", "roman_urdu")
    assert out["reply"] == agent.SAFE_PRICE_REPLY and "flag_owner" in out["tools_used"] and db.list_flags()


def test_owner_promise_without_flag_is_fixed(monkeypatch):
    replies = [NS(tool_calls=None, content="Maafi chahti hoon. Owner ko batate hain."),
               NS(tool_calls=[_call("flag_owner", {"reason": "wants lower price"}, 1)], content=""),
               NS(tool_calls=None, content="Owner ko bata diya hai, wo jald rabta karein ge.")]
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: replies.pop(0))
    out = agent.run_agent("03009990012", "roman_urdu")
    assert "flag_owner" in out["tools_used"] and db.list_flags() and not replies


def test_real_prices_budget_and_questions_pass_the_guard():
    phone = "03009990013"
    say(phone, "Mera budget 3000 hai")
    ok = "Rs 3,000 ke budget mein Chocolate Fudge Cake 1kg Rs 2,200 + delivery Rs 200 = Rs 2,400. Owner se baat karwaun?"
    assert agent.reply_problems(phone, ok, [], []) == []
    assert agent.reply_problems(phone, "Is pe 40% off milega", [], [])  # no product allows 40%


def test_confirm_messages_go_to_agent_not_faq():
    import main
    for text in ("Haan, confirm", "confirm kar dein", "ji", "G kar do"):
        assert main.looks_like_confirm(text), text
    assert not main.looks_like_confirm("Delivery charges kitne hain?")


def _orders(phone, n):
    db.upsert_customer(phone, {"name": "Ayesha", "addresses": [GOOD], "total_orders": n, "cancelled_orders": 0})


def test_loyalty_every_5th_order_gets_10_percent_and_does_not_stack():
    phone = "03009990014"
    _orders(phone, 3)
    assert tools.loyalty(phone)["orders_until_reward"] == 1 and not tools.loyalty(phone)["eligible"]
    _orders(phone, 4)  # next one is the 5th order
    r = tools.loyalty(phone)
    assert r["eligible"] and r["percent"] == 10 and r["order_number"] == 5
    tools.check_discount(phone, "p7")
    tools.check_discount(phone, "p7")  # cookies allow 15% by bargaining: bigger than the 10% reward
    s = tools.preview_order(phone, [{"product_id": "p7", "quantity": 1}, {"product_id": "p8", "quantity": 1}],
                            "Ayesha", GOOD, future())["summary"]
    cookies, cupcakes = s["items"]
    assert cookies["discount_percent"] == 15 and cupcakes["discount_percent"] == 10  # never 15 + 10
    assert s["loyalty_percent"] == 10 and s["total"] == 638 + 1080 + 200


def test_loyalty_counts_cancelled_orders_out_and_owner_can_turn_it_off():
    phone = "03009990015"
    db.upsert_customer(phone, {"name": "Bilal", "total_orders": 5, "cancelled_orders": 1})
    assert tools.loyalty(phone)["eligible"]  # 4 real orders -> next is the 5th
    shop = db.get_shop()
    db.save_catalog(dict(shop, loyalty_every=0), db.get_products(), db.get_faqs())
    assert not tools.loyalty(phone)["active"]


def test_returning_customer_info_has_saved_name_address_and_loyalty():
    phone = "03009990016"
    _orders(phone, 4)
    info = agent.customer_info(phone)
    assert "Saved name: Ayesha" in info and GOOD in info and "5th order" in info and "10% off" in info


def test_check_karte_hain_stall_and_typo_discount_are_nudged(monkeypatch):
    """'ptice kam?' labelled faq, and Super only said 'Discount ke liye check karte hain' (Oct 26 live test)."""
    seen = []

    def fake(model, messages, tl):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return NS(tool_calls=None, content="Discount ke liye check karte hain.")
        if len(seen) == 2:
            return NS(tool_calls=None, content="Ji, abhi batate hain.")
        if len(seen) == 3:
            return NS(tool_calls=[_call("check_discount", {"product_id": "p8"}, 1)], content="")
        return NS(tool_calls=None, content="Aap ke liye 5% kam: Rs 1,140.")

    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", fake)
    phone = "03009990017"
    say(phone, "ptice kam?")
    out = agent.run_agent(phone, "roman_urdu", "faq")
    assert agent.is_stall("Discount ke liye check karte hain.")
    assert "check_discount" in out["tools_used"] and out["reply"].endswith("Rs 1,140.")


def test_product_ids_never_reach_the_customer(monkeypatch):
    """Oct 26 live test: the menu reply showed 'Chocolate Cake 1kg - Rs 2,200 [p1]'."""
    import main
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    monkeypatch.setattr(ai, "answer_faq", lambda *a, **k: "Chocolate Fudge Cake 1kg - Rs 2,200 [p1]\nCookies - Rs 750 [p7]")
    out = main.handle_message("03009990020", "Menu bhej dein")
    assert "[p" not in out.reply and "Rs 2,200" in out.reply


def test_slow_agent_stops_before_server_timeout(monkeypatch):
    """If Nebius is very slow, the agent stops, alerts the owner and still replies."""
    clock = iter([0, 0, 31, 31, 31])
    monkeypatch.setattr(agent.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(content="", tool_calls=[_call("get_products", {}, 1)]))
    out = agent.run_agent("03009990021", "roman_urdu")
    assert out["tools_used"] == ["get_products"] and out["reply"] and db.list_flags()


def test_ai_client_has_no_hidden_retries(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test")
    ai._clients.clear()
    assert ai.client().max_retries == 0


# ------------------------------------------------------------------ FAQ answers are checked in code (Oct 26 Noor test)
def _faq(monkeypatch, reply_json: str, language: str = "roman_urdu") -> str:
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat", lambda *a, **k: reply_json)
    shop = db.get_shop()
    return ai.answer_faq("q", language, db.shop_info_text(), shop["name"], shop.get("city", ""))


def test_faq_answer_with_real_evidence_is_sent(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, delivery Rs 200 hai.",
                                      "evidence": ["Delivery fee: Rs 200"]}))
    assert r == "Ji, delivery Rs 200 hai." and "[NEEDS_OWNER]" not in r


def test_faq_answer_in_english_letters_for_urdu_shop_is_sent(monkeypatch):
    """Oct 26 v11 live test: correct answers were blocked because Nano didn't copy Urdu-script lines exactly."""
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, shop subah 10 se raat 9 baje tak khulti hai.",
                                      "evidence": ["Timings: Daily 10am to 9pm"]}))
    assert r.startswith("Ji, shop")


def test_faq_plain_text_reply_is_still_checked(monkeypatch):
    assert _faq(monkeypatch, "Ji, delivery Rs 200 hai.") == "Ji, delivery Rs 200 hai."
    assert _faq(monkeypatch, "Ji, sugar-free bhi milta hai.").endswith("[NEEDS_OWNER]")


def test_faq_real_eggless_answer_from_shop_faq_is_sent(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, eggless Rs 300 extra mein, 2 din pehle.",
                                      "evidence": ["Yes, eggless is available for Rs 300 extra with 2 days notice."]}))
    assert r.startswith("Ji, eggless")


def test_faq_invented_discount_goes_to_owner(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer",
                                      "reply": "Refund nahi, lekin hum 10% se 15% discount dete hain.",
                                      "evidence": ["No refunds on custom cakes"]}))
    assert r.endswith("[NEEDS_OWNER]") and "%" not in r


def test_faq_wrong_price_goes_to_owner(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Chocolate cake Rs 1,500 ka hai.",
                                      "evidence": ["Chocolate Fudge Cake 1kg"]}))
    assert r.endswith("[NEEDS_OWNER]")


def test_faq_unclear_message_asks_back_without_owner(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "clarify", "reply": "Ji, aap ka matlab kya hai?", "evidence": []}))
    assert r == "Ji, aap ka matlab kya hai?"


def test_faq_unknown_uses_fixed_owner_line_in_customer_language(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "unknown", "reply": "Policy nahi hai lekin 10% de dete hain"}), "urdu")
    assert r.startswith("جی") and r.endswith("[NEEDS_OWNER]") and "10%" not in r


def test_faq_plain_text_with_owner_tag_goes_to_owner(monkeypatch):
    r = _faq(monkeypatch, "Ye owner batayenge. [NEEDS_OWNER]")
    assert r.endswith("[NEEDS_OWNER]")


def test_faq_works_with_urdu_script_shop_info():
    info = "Shop: نور بیکری\nTimings: صبح 9 سے رات 10 بجے تک\nDelivery fee: Rs 200"
    kind, problems = ai.check_faq_answer({"type": "answer", "reply": "Subah 9 se raat 10 baje tak.",
                                          "evidence": ["صبح 9 سے رات 10 بجے تک"]}, info)
    assert kind == "answer" and not problems


def test_faq_claim_with_unrelated_evidence_goes_to_owner(monkeypatch):
    """Sugar-free is not in the bakery's info, so quoting a real price line doesn't make the claim true."""
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, Chocolate Fudge Cake sugar-free bhi milta hai.",
                                      "evidence": ["Chocolate Fudge Cake 1kg: Rs 2,200"]}))
    assert r.endswith("[NEEDS_OWNER]")


def test_faq_can_mention_the_real_loyalty_offer(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, offer hai: har 5th order pe 10% discount.",
                                      "evidence": ["every 5th order gets 10% off"]}))
    assert r.startswith("Ji, offer hai")


def test_agent_invented_refund_policy_is_never_sent(monkeypatch):
    """Oct 26 Noor test: Super wrote a refund/replacement policy the shop never wrote down."""
    monkeypatch.setattr(ai, "MOCK", False)
    shop = db.get_shop()
    db.save_catalog(dict(shop, policies=""), db.get_products(), [])  # a shop with no written policy
    bad = NS(tool_calls=None, content="We don't process refunds. Contact us within 2 hours and we'll replace the item.")
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: bad)
    out = agent.run_agent("03009990030", "roman_urdu", "complaint")
    assert out["reply"] == ai.OWNER_WILL_CONFIRM["roman_urdu"] and "flag_owner" in out["tools_used"]


def test_agent_real_policy_from_shop_info_is_allowed():
    phone = "03009990031"
    ok = "Custom cakes pe refund nahi hota, maafi chahti hoon."
    assert agent.reply_problems(phone, ok, [], []) == []  # bakery policy: "No refunds on custom cakes"


def test_faq_history_leaves_out_owner_will_confirm_lines(monkeypatch):
    import main
    seen = {}
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    monkeypatch.setattr(ai, "answer_faq", lambda *a, history="", **k: seen.setdefault("h", history) or "Ji.")
    phone = "03009990032"
    db.add_message(phone, "customer", "Eggless?")
    db.add_message(phone, "assistant", ai.OWNER_WILL_CONFIRM["roman_urdu"])
    main.handle_message(phone, "Timing?")
    assert "Eggless?" in seen["h"] and "owner se confirm" not in seen["h"]
