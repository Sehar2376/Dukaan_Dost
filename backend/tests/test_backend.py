Claude
/
Ran 5 commands
I’m on the owner-takeover problem now. I found that the AI sees the owner’s messages as if it had written them itself, and I’m checking how the price guard treats them.

Ran 8 commands, shared files, used a tool
Dukaan Dost: Test Log, 27 Oct (what was tested, results, what is left)
Claude Docs
·Only you
I went through all 37 images again and built the owner-takeover fix. Nothing is uploaded; the final 7 files are attached, and all 132 tests pass.

I put the full test log in a new doc, Dukaan Dost: Test Log, 27 Oct. It has 10 sections covering questions, ordering, addresses and times, confirming, bargaining, complaints, languages, system, the takeover fix and what is still untested. I did not edit your older 191-row Noor doc; the log is a separate doc.

Your earlier fixes are safe. I compared my files with what is on GitHub right now. Every line I removed was replaced by a better version, and no earlier fix was dropped. The only deleted lines were the old versions of the check, the alert text, the discount rule and the FAQ call. These files stack on top of your thanks upload, so do not re-upload the old agent.py, or you will undo them.

Owner takeover fix. I found two causes:

The AI saw the owner’s messages as its own replies, so it didn’t know the owner had already answered.
The price guard blocked any price the owner typed, because it was not in the menu. The bot then said “owner se confirm karti hoon” again.
Now the owner’s words count as final. The AI sees them, may repeat the owner’s price, and must not say the owner will confirm something already answered. This works on both the order path and the question path. A price the owner never said is still blocked.

One limit: the saved order total still comes from the menu. If the owner quotes a special price, check the order in Orders.

How to upload (use the folder links from before)

backend folder: agent.py, ai.py, main.py, tools.py.
backend/prompts folder: agent.txt, faq.txt.
backend/tests folder: test_backend.py.
README.md pencil ✏️: change 120 to 132.
Retest after the deploy. Use New customer for each:

Haan, confirm on a full order should show a real order number.
The 5% → 10% → “bas 2%” bargaining should stay at Rs 1,530.
“aj raat 11 baja” should be refused.
Take over a chat, type a price as the owner, switch back to the AI, and ask about the price. It should use your price.
Agent
PY
Ai
PY
Main
PY
Tools
PY
Agent
TXT
Faq
TXT
Test backend
PY
share-1793122727594-All-PDF-Reader-20261027-22.38.35.pdf
share-1793122727594-All-PDF-Reader-20261027-
22.38.35
.pdf
PDF
take a look at this too

Ran 5 commands
I’m reading the remaining pages of this PDF now. The first 8 are older phone chats, and the rest are laptop photos.

Read 5 files, ran a command
I’m fixing the issues from this new PDF now: raw JSON shown to a customer, the bot switching between male and female speech, dates like “2026-10-28 09:00”, and the false “Menu restore ho gaya”.

Ran 3 commands, shared files
I read all 13 pages of the new PDF and fixed what I found. The same 7 files are attached again, now including these new fixes. Please use these and discard the earlier set. All 135 tests pass.

What the PDF showed (8 phone chats from earlier today and 5 laptop photos taken at 21:17 to 22:27):

Found	Fix
Raw JSON shown to a customer ({"type": "answer", "reply": ... "evidence": [...]) on the England and Germany delivery questions. The AI’s answer was cut off, and the broken text was sent as is.	Cut-off JSON is never sent now. The reply text is taken out of it, or the customer gets the safe “owner confirm” reply. I also gave the AI more room to finish.
The bot spoke as a man and a woman: “karta hoon”, “deta hoon”, “doonga”, “samajh gaya” beside “batati hoon”.	Code now converts these to female forms in every Roman Urdu or Urdu reply, and the prompts ask for it.
“Menu restore ho gaya” after a customer typed “restore sample menu”. The bot cannot do that.	A reply claiming a menu, price or settings change is replaced with “Only the owner can change the menu.”
“Earliest delivery: Kal (Wednesday) 2026-10-28 09:00”	Dates now read “28 Oct, 9:00 am”.
“Chocolate cake thora kam kar dein” while chocolate was out of stock. The bot then offered 5% off pineapple, which the customer never chose.	New prompt rule: no discount on a different item the customer didn’t choose.
“Owner ko alert karne ki zaroorat nahi thi” and “Roman Urdu mein hi jawab doonga” shown to customers.	New prompt rule: never explain the inside workings.
Old replies ended with “Shukriya!” on every message, and “ek din pehle order” was invented.	Both were already fixed in your earlier uploads.
Good in this PDF: the earlier no-delivery answers for England and Germany were correct in content. “Malir delivery nahi hoti” on the sample bakery is correct, since the bakery’s areas are Gulshan, Johar and Nazimabad.

Still weak, not fixed: “50 cake” got “Bilkul jee! 50 pineapple cakes... Apka naam Fatima hai”, which assumed pineapple and used a saved name. Please retest this one after the deploy.

How to upload (the folder links are the same as before)

backend folder: agent.py, ai.py, main.py, tools.py.
backend/prompts folder: agent.txt, faq.txt.
backend/tests folder: test_backend.py.
README.md pencil ✏️: change 120 to 135.
I’ll also add this PDF’s findings to the Test Log doc if you want.

Agent
PY
Ai
PY
Main
PY
Tools
PY
Agent
TXT
Faq
TXT
Test backend
PY




Projects
Viewers don’t see new messages. Update Shared Chat
Test backend · PY
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
    say(phone, "kam karo")
    first = tools.check_discount(phone, "p2", 50)        # max is 10%
    say(phone, "aur kam")
    second = tools.check_discount(phone, "p2", 90)
    say(phone, "plz aur kam")
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
    say("03009990003", "Thora kam kar dein")
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
    say(phone, "kam karo")
    tools.check_discount(phone, "p8")
    say(phone, "aur kam")
    tools.check_discount(phone, "p8")  # 10% agreed -> Rs 1,080
    say(phone, "theek hai, total batao")
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
    say(phone, "cookies kam karo")
    tools.check_discount(phone, "p7")
    say(phone, "aur kam")
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
 
 
def test_price_and_menu_questions_never_end_in_owner_confirm(monkeypatch):
    """Oct 27 Noor test: 'Menu bhej dein' and 'Chocolate cake kitne ka hai?' got 'owner se confirm karti hoon'."""
    import main
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "over_budget", lambda: False)
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    monkeypatch.setattr(ai, "answer_faq", lambda *a, **k: ai.OWNER_WILL_CONFIRM["roman_urdu"] + " [NEEDS_OWNER]")
    for i, text in enumerate(("Menu bhej dein", "Chocolate cake 1kg kitne ka hai?", "rate list?")):
        out = main.handle_message(f"0300999004{i}", text)
        assert "Rs 2,200" in out.reply and "Delivery: Rs 200" in out.reply and not out.needs_owner, text
        assert "Lotus" not in out.reply  # out of stock items are left out
    out = main.handle_message("03009990049", "Eggless cake banate hain?")
    assert out.needs_owner  # not a price question: still goes to the owner
 
 
def test_price_question_words():
    import main
    for t in ("Menu bhej dein", "kitne ka hai", "price?", "Cake ki qeemat", "کیک کی قیمت"):
        assert main.PRICE_QUESTION.search(t), t
    for t in ("Cake kitne din pehle order karna hoga?", "Eggless?", "Delivery kab hogi"):
        assert not main.PRICE_QUESTION.search(t), t
 
 
def test_agent_never_invents_a_quantity_limit_or_custom_rule(monkeypatch):
    """Oct 27 tests: '20 cakes' -> 'maximum limit 8000 rupees hai'; 'Happy Birthday likh dein' -> 'Custom text nahi'."""
    phone = "03009990050"
    assert "never invent a maximum or minimum" in ai.load_prompt("agent.txt")
    assert agent.reply_problems(phone, "Ye maximum discount hai: Rs 1,080.", [], []) == []
    shop = db.get_shop()
    db.save_catalog(dict(shop, policies=""), db.get_products(), [])
    assert agent.reply_problems(phone, "Custom text nahi kar sakte.", [], [])
 
 
def test_agent_never_says_flag_to_the_customer():
    assert agent.reply_problems("03009990051", "Ji, owner se poochte hain. Flag kar dete hain.", ["flag_owner"], [])
    assert agent.reply_problems("03009990051", "Ji, owner ko bata diya hai, wo jald rabta karein ge.", ["flag_owner"], []) == []
 
 
# ------------------------------------------------------------------ Oct 27 Noor test: narration, false cancel, English
def test_narration_sentences_are_removed():
    assert agent.clean_reply("Flag owner. Owner ko bata diya hai jee, wo aap se rabta karein ge.") == \
        "Owner ko bata diya hai jee, wo aap se rabta karein ge."
    assert agent.clean_reply("I'll confirm the order now. Let me call confirm_order.") == ""
    assert agent.clean_reply("Customer abhi tak koi product select nahi kiya. Main unse poochta hoon. Jee?") == "Jee?"
    assert agent.clean_reply("Chocolate cake Rs 2,200 hai. Order karna hai?") == "Chocolate cake Rs 2,200 hai. Order karna hai?"
 
 
def test_narration_only_reply_is_never_sent(monkeypatch):
    replies = [NS(tool_calls=None, content="Get products. Let me fetch prices."),
               NS(tool_calls=None, content="I'll get products info."),
               NS(tool_calls=None, content="Chocolate Fudge Cake 1kg Rs 2,200 hai ji.")]
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: replies.pop(0))
    out = agent.run_agent("03009990060", "roman_urdu")
    assert out["reply"] == "Chocolate Fudge Cake 1kg Rs 2,200 hai ji."
 
 
def test_narration_forever_alerts_owner_instead(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(tool_calls=None, content="Let me search for chocolate cake."))
    out = agent.run_agent("03009990061", "roman_urdu")
    assert "let me" not in out["reply"].lower() and db.list_flags()
 
 
def test_ai_never_claims_it_cancelled_an_order(monkeypatch):
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(tool_calls=None, content="Okay, order cancelled."))
    out = agent.run_agent("03009990062", "roman_urdu")
    assert out["reply"] == ai.OWNER_WILL_CONFIRM["roman_urdu"] and "flag_owner" in out["tools_used"]
 
 
def test_english_reply_to_roman_urdu_customer_is_flagged():
    long_en = "We haven't set up any items yet, let's build the order together. What would you like to order today?"
    assert agent.reply_problems("03009990063", long_en, [], [], "roman_urdu")
    assert agent.reply_problems("03009990063", long_en, [], [], "english") == []
    assert agent.reply_problems("03009990063", "Ji, aap kaunsa cake chahte hain?", [], [], "roman_urdu") == []
 
 
def test_order_details_always_go_to_the_agent():
    import main
    for t in ("Kal shaam 6 baje", "Raat 11 baje", "Address Gulshan", "Name Fatima", "Order cancel kar dein", "cash"):
        assert main.ORDER_DETAIL.search(t), t
    for t in ("Delivery charges kitne hain?", "Menu bhej dein", "Eggless cake banate hain?"):
        assert not main.ORDER_DETAIL.search(t), t
 
 
def test_discount_moves_one_step_per_customer_message():
    """Oct 27: nan khatai's first ask jumped straight to 15% because the AI called check_discount twice."""
    phone = "03009990070"
    say(phone, "Cookies pe discount?")
    first = tools.check_discount(phone, "p7")
    again = tools.check_discount(phone, "p7")  # same customer message: no extra step
    assert first["discount_percent"] == again["discount_percent"] == 8
    say(phone, "Aur kam?")
    assert tools.check_discount(phone, "p7")["discount_percent"] == 15
 
 
def test_short_product_name_goes_to_the_agent():
    import main
    assert main.names_a_product("Chocolate") and main.names_a_product("cupcakes")
    assert not main.names_a_product("Delivery charges kitne hain?") and not main.names_a_product("kya")
 
 
def test_preview_order_phrase_is_removed():
    assert agent.clean_reply("Preview order? Aap ka naam aur address bata dein.") == "Aap ka naam aur address bata dein."
 
 
# ------------------------------------------------------------------ Oct 27 Noor test, section 6
def test_payment_questions_answered_from_saved_methods(monkeypatch):
    import main
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    shop = db.get_shop()
    db.save_catalog(dict(shop, payment_methods=["Cash on delivery", "JazzCash"]), db.get_products(), db.get_faqs())
    r = main.handle_message("03009990080", "Easypaisa chalega?").reply
    assert r.startswith("Maaf kijiye, Easypaisa abhi nahi lete") and "JazzCash" in r
    assert main.handle_message("03009990081", "Bank transfer?").reply.startswith("Maaf kijiye, bank transfer")
    assert main.handle_message("03009990082", "JazzCash chalega?").reply.startswith("Ji, Payment")
    assert not main.PAYMENT_QUESTION.search("JazzCash se dunga")  # an order detail, not a question
 
 
def test_faq_invented_delivery_time_and_halal_go_to_owner(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Delivery ke liye 2 se 3 din ka intezaar karna padega."}))
    assert r.endswith("[NEEDS_OWNER]")
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Ji, sab cheez halal hai."}))
    assert r.endswith("[NEEDS_OWNER]")
 
 
def test_faq_real_notice_time_is_allowed(monkeypatch):
    r = _faq(monkeypatch, json.dumps({"type": "answer", "reply": "Cakes ke liye 1 day pehle order karein."}))
    assert r.startswith("Cakes")  # the bakery's info says "Cakes need 1 day advance notice"
 
 
def test_offer_question_tells_the_loyalty_reward(monkeypatch):
    import main
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "bargain", "urgent": False})
    r = main.handle_message("03009990090", "Koi offer hai?").reply
    assert r.startswith("Ji haan! Har 5th order pe 10% discount")
    shop = db.get_shop()
    db.save_catalog(dict(shop, loyalty_every=0), db.get_products(), db.get_faqs())
    assert "koi offer nahi" in main.handle_message("03009990091", "Koi offer hai?").reply
    assert not main.OFFER_QUESTION.search("Thora kam kar dein")
 
 
# ------------------------------------------------------------------ Oct 27 Noor test, section 7
def test_order_limit_claim_is_never_sent():
    assert agent.reply_problems("03009990100", "Too big - max limit Rs 8,000. Suggest fewer.", [], [])
    assert agent.reply_problems("03009990100", "Ye maximum discount hai: Rs 1,080.", [], []) == []
 
 
def test_changing_the_item_never_triggers_a_discount(monkeypatch):
    """'Pineapple kar dein' was labelled bargain and the code forced a discount."""
    seen = []
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: seen.append(1) or NS(tool_calls=None, content="Ji, pineapple cake Rs 1,800. Kitne chahiye?"))
    say("03009990101", "Pineapple kar dein")
    out = agent.run_agent("03009990101", "roman_urdu", "bargain")
    assert "check_discount" not in out["tools_used"] and len(seen) == 1
 
 
def test_ai_cannot_lock_the_price_with_its_own_percent():
    phone = "03009990102"
    say(phone, "kam karo")
    tools.check_discount(phone, "p1")
    say(phone, "aur kam")
    second = tools.check_discount(phone, "p1", requested_percent=5)  # the AI passed 5, the customer never said 5%
    assert second["discount_percent"] == 10
    say(phone, "bas 2% kam kar do")
    p = "03009990103"
    say(p, "bas 2% kam kar do")
    assert tools.check_discount(p, "p1", requested_percent=2)["discount_percent"] == 2
 
 
def test_flagged_owner_sentence_removed_and_short_english_caught():
    assert agent.clean_reply("Flagged owner. Owner aap se jald rabta karein ge.") == "Owner aap se jald rabta karein ge."
    assert agent.sounds_english("We need quantities. How many of each? Shukriya!")
    assert not agent.sounds_english("Ji, kitne chahiye? Shukriya!")
 
 
def test_agent_prompt_says_everything_means_one_of_each():
    assert "1 of each in-stock item" in ai.load_prompt("agent.txt")
 
 
# ------------------------------------------------------------------ one-tap stock toggle (Settings)
def test_owner_marks_item_sold_out_and_available_again():
    r = client.patch("/products/p1", json={"in_stock": False})
    assert r.status_code == 200 and r.json()["in_stock"] is False
    assert "OUT OF STOCK" in db.shop_info_text().split("[p1]")[1].split("\n")[0]
    res = tools.preview_order("03009990110", [{"product_id": "p1", "quantity": 1}], "Ali", GOOD, future())
    assert not res["ok"] and "out of stock" in res["problems"][0]
    assert client.patch("/products/p1", json={"in_stock": True}).json()["in_stock"] is True
    assert client.patch("/products/nope", json={"in_stock": True}).status_code == 404
 
 
# ------------------------------------------------------------------ v16: honest orders, calm style, clean alerts
def test_smaller_percent_never_raises_the_price():
    phone = "03009990200"
    say(phone, "kam karo")
    assert tools.check_discount(phone, "p2")["discount_percent"] == 5
    say(phone, "aur kam")
    assert tools.check_discount(phone, "p2")["discount_percent"] == 10
    say(phone, "bas 2% kam karde")
    r = tools.check_discount(phone, "p2", 2)
    assert r["discount_percent"] == 10  # never back up to a smaller discount
 
 
def test_false_order_claims_are_caught():
    phone = "03009990201"
    for bad in ("Order placed. Your order # is ready.", "Order save hogaya ji, number SMS se aayega.",
                "Order confirmed. Cash on delivery."):
        assert agent.reply_problems(phone, bad, [], [], "roman_urdu"), bad
    saved = [{"ok": True, "order_id": "ORD-7"}]
    assert agent.reply_problems(phone, "Order confirm ho gaya. Aap ka order number ORD-7 hai.", ["confirm_order"],
                                saved, "roman_urdu") == []
    assert agent.reply_problems(phone, "Order confirm kar dein?", [], [], "roman_urdu") == []  # a question is fine
 
 
def test_style_slips_are_detected_and_tidied():
    phone = "03009990202"
    assert agent.reply_problems(phone, "Name? Address? Confirm 2 pineapple cakes.", [], [], "roman_urdu")
    assert agent.reply_problems(phone, "Ji, order number SMS se aayega.", [], [], "roman_urdu")
    assert agent.clean_reply("Let's preview with current info anyway? Aap ka naam kya hai?") == "Aap ka naam kya hai?"
    assert agent.clean_reply("Proceeding normally. Ask details. Ji, address batayein.") == "Ji, address batayein."
    assert agent.tidy("System says address issue. Ji, address dobara batayein.") == "Ji, address dobara batayein."
 
 
def test_owner_notes_hide_internal_checks():
    notes = [agent.owner_note([f"'Eggless' {agent.NOT_IN_SHOP} - never promise it; call flag_owner"]),
             agent.owner_note(["you told the customer about the owner but did not call flag_owner"]),
             agent.owner_note(["Rs 1,666 is not a price the system allows"]),
             agent.owner_note([agent.FALSE_ORDER])]
    for n in notes:
        assert "flag_owner" not in n and "confirm_order" not in n and "system" not in n.lower() and "Roman Urdu" not in n
 
 
def test_order_number_is_always_shown():
    out = agent.with_order_number("Order confirm ho gaya.", [{"ok": True, "order_id": "ORD-9"}], "roman_urdu")
    assert "ORD-9" in out
    assert agent.with_order_number("Order ORD-9 confirm.", [{"ok": True, "order_id": "ORD-9"}], "roman_urdu") == "Order ORD-9 confirm."
    assert agent.with_order_number("Ji, cake Rs 2,000 hai.", [], "roman_urdu") == "Ji, cake Rs 2,000 hai."
 
 
def test_clock_time_reading():
    assert agent.clock_time("aj raat 11 baja") == "23:00"
    assert agent.clock_time("kal shaam 6 baje") == "18:00"
    assert agent.clock_time("kal 3am par") == "03:00"
    assert agent.clock_time("28 oct 5pm") == "17:00"
    assert agent.clock_time("6 baje") is None  # not clear enough: the order agent asks
 
 
HOURS = {d: ["09:00", "22:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
 
 
def test_false_order_twice_gives_honest_reply_without_alert(monkeypatch):
    phone = "03009990203"
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(tool_calls=None, content="Order placed. Your order # is ready."))
    say(phone, "haan confirm")
    out = agent.run_agent(phone, "roman_urdu", "order")
    assert out["reply"] == agent.NOT_SAVED_REPLY["roman_urdu"] and "flag_owner" not in out["tools_used"]
 
 
def test_style_slip_twice_is_sent_without_alert(monkeypatch):
    phone = "03009990204"
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", lambda m, msgs, tl: NS(tool_calls=None, content="Name? Address? Time? Payment?"))
    say(phone, "pineapple chahiye")
    out = agent.run_agent(phone, "roman_urdu", "order")
    assert out["reply"] and "flag_owner" not in out["tools_used"]
 
 
def test_time_outside_shop_hours_is_refused_early(monkeypatch):
    phone = "03009990205"
    shop = dict(db.get_shop(), opening_hours=HOURS)
    monkeypatch.setattr(db, "get_shop", lambda: shop)
    seen = []
 
    def fake(model, messages, tl):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return NS(tool_calls=None, content="Aj raat 11 baje delivery ho jayegi. Address batayein.")
        return NS(tool_calls=None, content="Maaf kijiye, raat 11 baje delivery possible nahi, hum 9 se 10 tak hain.")
 
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat_with_tools", fake)
    say(phone, "aj raat 11 baja")
    out = agent.run_agent(phone, "roman_urdu", "order")
    assert "outside shop hours" in seen[1] and "possible nahi" in out["reply"]
 
 
# ------------------------------------------------------------------ v16b: after an owner takeover the owner's word is final
def test_owner_quoted_price_is_allowed_and_shown_to_the_ai():
    phone = "03009990210"
    say(phone, "kal ke liye 3 chocolate cake ka kitna hoga?")
    db.add_message(phone, "owner", "Ji, 3 cakes ka Rs 5,400 ho jayega, delivery free.")
    amounts, percents = agent.allowed_numbers(phone, [])
    assert 5400 in amounts
    assert agent.reply_problems(phone, "Owner ne bataya hai ke 3 cakes Rs 5,400 mein milen ge.", [], [], "roman_urdu") == []
    msgs = agent.build_messages(phone, "roman_urdu")
    assert "THE OWNER ALREADY WROTE" in msgs[0]["content"] and "5,400" in msgs[0]["content"]
 
 
def test_price_not_said_by_owner_is_still_blocked():
    phone = "03009990211"
    say(phone, "cake kitne ka?")
    assert agent.reply_problems(phone, "Cake Rs 7,321 ka hai.", [], [], "roman_urdu")  # nobody said 7,321
 
 
def test_faq_path_receives_owner_words_after_takeover(monkeypatch):
    import main
    phone = "03009990212"
    seen = {}
 
    def fake_faq(message, language, shop_info, shop_name, city, history="", owner_said=""):
        seen["owner_said"], seen["history"] = owner_said, history
        return "Ji, owner ke mutabiq Rs 5,400 hai."
 
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "answer_faq", fake_faq)
    monkeypatch.setattr(ai, "classify", lambda m: {"language": "roman_urdu", "intent": "faq", "urgent": False})
    say(phone, "kitne ka hoga?")
    db.add_message(phone, "owner", "Rs 5,400 ho jayega.")
    TestClient(main.app).post("/chat", json={"phone": phone, "message": "aur batayein kya hoga?"})
    assert "5,400" in seen.get("owner_said", "") and "Owner: Rs 5,400" in seen["history"]
 
 
# ------------------------------------------------------------------ v16c: one voice, readable dates, no raw JSON, no fake actions
def test_polish_speaks_as_a_woman_and_reads_dates():
    p = agent.polish_reply
    assert p("Main dobara try karta hoon.", "roman_urdu") == "Main dobara try karti hoon."
    assert p("Jaldi jawab deta hoon. Main samajh gaya.", "roman_urdu") == "Jaldi jawab deti hoon. Main samajh gayi."
    assert p("Roman Urdu mein hi jawab doonga.", "roman_urdu") == "Roman Urdu mein hi jawab doongi."
    assert p("Earliest delivery: 2026-10-28 09:00.", "roman_urdu") == "Earliest delivery: 28 Oct, 9:00 am."
    assert p("I will do it. 2026-10-28 18:30", "english") == "I will do it. 28 Oct, 6:30 pm"  # English wording untouched
    assert p("Aap ka order ho jayega.", "roman_urdu") == "Aap ka order ho jayega."
 
 
def test_cannot_claim_to_change_menu_or_settings():
    assert agent.polish_reply("Menu restore ho gaya. Ab kya lenge?", "roman_urdu") == agent.CANT_CHANGE["roman_urdu"]
    assert agent.polish_reply("Price update kar diya.", "roman_urdu") == agent.CANT_CHANGE["roman_urdu"]
    assert agent.polish_reply("Ji, menu yeh hai: Cake Rs 2,000.", "roman_urdu") == "Ji, menu yeh hai: Cake Rs 2,000."
 
 
def test_cut_off_json_is_never_shown_to_the_customer(monkeypatch):
    cut = '{"type": "answer", "reply": "Ji, hum England mein delivery nahi karte.", "evidence": ["abc", "def'
    monkeypatch.setattr(ai, "MOCK", False)
    monkeypatch.setattr(ai, "chat", lambda *a, **k: cut)
    out = ai.answer_faq("England delivery?", "roman_urdu", db.shop_info_text(), "Noor", "Karachi")
    assert "{" not in out and "evidence" not in out
 










