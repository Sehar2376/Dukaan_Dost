"""All calls to NVIDIA Nemotron models on Nebius Token Factory live here.

- Nemotron 3 Nano  -> fast, cheap calls (classify language/intent, FAQ replies)
- Nemotron 3 Super -> reasoning + tool calling (orders, bargaining, menu setup)
- Nemotron 3 Ultra -> deep reasoning for rare, heavy jobs (monthly business advice, on request)

Set MOCK_AI=1 in .env to run without an API key (keyword-based fake, for UI work only).
"""
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROMPTS = Path(__file__).parent / "prompts"
MOCK = os.getenv("MOCK_AI", "0") == "1" or not os.getenv("NEBIUS_API_KEY")

NANO = os.getenv("NEMOTRON_NANO_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
SUPER = os.getenv("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
ULTRA = os.getenv("NEMOTRON_ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b")

BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
# Ultra is listed in the us-central1 region. If the main address doesn't serve it, we try this one.
ULTRA_BASE_URL = os.getenv("NEBIUS_ULTRA_BASE_URL", "https://api.tokenfactory.us-central1.nebius.com/v1/")

_clients: dict = {}


def client(base_url: str | None = None):
    """One OpenAI-style client per address, created once."""
    url = base_url or BASE_URL
    if url not in _clients:
        from openai import OpenAI

        _clients[url] = OpenAI(base_url=url, api_key=os.environ["NEBIUS_API_KEY"], timeout=30)
    return _clients[url]


# Price per 1M tokens in USD (input, output). Check the Token Factory pricing page and
# override in .env if they differ. Used only to ESTIMATE spend for the /usage page and budget.
PRICES = {
    "nano": (float(os.getenv("PRICE_NANO_IN", "0.06")), float(os.getenv("PRICE_NANO_OUT", "0.24"))),
    "super": (float(os.getenv("PRICE_SUPER_IN", "0.30")), float(os.getenv("PRICE_SUPER_OUT", "0.90"))),
    "ultra": (float(os.getenv("PRICE_ULTRA_IN", "1.00")), float(os.getenv("PRICE_ULTRA_OUT", "3.00"))),
}
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "1.50"))


def _tier(model: str) -> str:
    m = model.lower()
    return "nano" if "nano" in m else "ultra" if "ultra" in m else "super"


def record_usage(model: str, response) -> None:
    """Count tokens and estimated cost of one call into today's usage document."""
    import db  # local import avoids a circular import

    u = getattr(response, "usage", None)
    pin, pout = (getattr(u, "prompt_tokens", 0) or 0), (getattr(u, "completion_tokens", 0) or 0)
    tier = _tier(model)
    cost = pin / 1e6 * PRICES[tier][0] + pout / 1e6 * PRICES[tier][1]
    db.add_usage({"ai_calls": 1, "prompt_tokens": pin, "completion_tokens": pout, "cost_usd": cost,
                  f"{tier}_calls": 1, f"{tier}_cost_usd": cost})


def over_budget() -> bool:
    """True when today's estimated spend has reached DAILY_BUDGET_USD (protects the credit)."""
    import db

    return db.get_usage().get("cost_usd", 0) >= DAILY_BUDGET_USD


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def strip_thinking(text: str) -> str:
    """Nemotron can emit <think>...</think> reasoning. Remove it before using the answer."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "</think>" in text:  # opening tag was dropped by the server
        text = text.split("</think>", 1)[1]
    return text.strip()


def extract_json(text: str) -> dict:
    """Pull the first {...} object out of a model reply (handles code fences / extra words)."""
    text = strip_thinking(text)
    text = re.sub(r"```(?:json)?", "", text)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"No JSON in model reply: {text[:200]!r}")
    return json.loads(match.group(0))


def chat(model: str, system: str, user: str, temperature: float = 0.2, max_tokens: int = 400,
         thinking: bool = False, base_url: str | None = None, retries: int = 2, timeout: float = 30) -> str:
    """One chat completion with a single retry (NFR-08). Returns plain text.

    thinking=False keeps fast calls fast and cheap; Ultra advice uses thinking=True."""
    last_err = None
    for attempt in range(retries):
        try:
            r = client(base_url).with_options(timeout=timeout).chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
            )
            record_usage(model, r)
            return strip_thinking(r.choices[0].message.content)
        except Exception as e:  # network error, timeout, 5xx...
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"Token Factory call failed: {last_err}")


def chat_with_tools(model: str, messages: list[dict], tools: list[dict]):
    """One step of the agent loop. Returns the assistant message (may contain tool_calls)."""
    last_err = None
    for attempt in range(2):
        try:
            r = client().chat.completions.create(
                model=model, messages=messages, tools=tools, tool_choice="auto",
                temperature=0.2, max_tokens=700,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            record_usage(model, r)
            return r.choices[0].message
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"Token Factory call failed: {last_err}")


# ---------------------------------------------------------------- classify
VALID_LANG = {"urdu", "roman_urdu", "english", "mixed"}
VALID_INTENT = {"faq", "order", "booking", "bargain", "complaint", "greeting", "abuse", "other"}
FALLBACK = {"language": "roman_urdu", "intent": "other", "urgent": False}


def _clean(d: dict) -> dict:
    return {
        "language": d.get("language") if d.get("language") in VALID_LANG else "roman_urdu",
        "intent": d.get("intent") if d.get("intent") in VALID_INTENT else "other",
        "urgent": bool(d.get("urgent", False)),
    }


def classify(message: str) -> dict:
    """Nano: detect language + intent + urgency. Always returns a valid dict."""
    if MOCK:
        return mock_classify(message)
    system = load_prompt("classify.txt")
    for attempt in range(2):
        try:
            extra = "" if attempt == 0 else "\nReturn ONLY the JSON object, nothing else."
            raw = chat(NANO, system + extra, message, temperature=0, max_tokens=80)
            return _clean(extract_json(raw))
        except (ValueError, json.JSONDecodeError):
            continue
        except RuntimeError:
            break
    return dict(FALLBACK, error=True)


# ---------------------------------------------------------------- FAQ reply
LANG_INSTRUCTIONS = {
    "roman_urdu": "Roman Urdu (Urdu written in English letters), like the customer.",
    "urdu": "Urdu script.",
    "english": "Simple English.",
    "mixed": "The same mix of Roman Urdu and English the customer used.",
}


def answer_faq(message: str, language: str, shop_info: str, shop_name: str, city: str) -> str:
    """Nano: answer a question using only saved shop info."""
    if MOCK:
        return "(mock) Ji, delivery Rs 200 hai. Owner jald confirm kar dein ge."
    system = load_prompt("faq.txt").format(
        shop_name=shop_name,
        city=city,
        language_instruction=LANG_INSTRUCTIONS.get(language, LANG_INSTRUCTIONS["roman_urdu"]),
        shop_info=shop_info,
    )
    return chat(NANO, system, message, temperature=0.3, max_tokens=250)


# ---------------------------------------------------------------- owner setup (F5)
def parse_shop_text(text: str) -> dict:
    """Super: turn the owner's messy pasted text into shop + products + faqs JSON."""
    if MOCK:
        return {"shop": {"name": "Mock Shop", "city": "Karachi", "timings": "10am-9pm",
                         "delivery_areas": ["Gulshan-e-Iqbal"], "delivery_fee": 200,
                         "payment_methods": ["Cash on delivery"], "policies": "", "large_order_threshold": 8000},
                "products": [{"name": "Chocolate cake 1kg", "price": 2200, "cost_price": None,
                              "max_discount_percent": 10, "in_stock": True, "category": "cake"}],
                "faqs": []}
    raw = chat(SUPER, load_prompt("setup.txt"), text, temperature=0, max_tokens=3000)
    return extract_json(raw)


# ---------------------------------------------------------------- summaries (F8)
def summary_note(numbers: dict, period: str, language: str = "roman_urdu") -> str:
    """Nano: 2-3 sentence explanation of numbers that were calculated in code."""
    if MOCK:
        return f"(mock) {period}: {numbers.get('orders', 0)} orders, Rs {numbers.get('sales', 0):,} sales."
    system = load_prompt("summary.txt").format(
        period=period, language_instruction=LANG_INSTRUCTIONS.get(language, LANG_INSTRUCTIONS["roman_urdu"]))
    return chat(NANO, system, json.dumps(numbers, ensure_ascii=False), temperature=0.3, max_tokens=200)


# ---------------------------------------------------------------- monthly business advice (Ultra)
def _clean_advice(d: dict) -> dict:
    tips = []
    for t in (d.get("tips") or [])[:5]:
        if isinstance(t, dict) and t.get("title") and t.get("detail"):
            tips.append({"title": str(t["title"])[:120], "detail": str(t["detail"])[:600],
                         "based_on": str(t.get("based_on", ""))[:200]})
    if not tips:
        raise ValueError("No usable tips in model reply")
    return {"headline": str(d.get("headline", ""))[:200], "tips": tips}


def business_advice(insights: dict, period: str, language: str = "english") -> dict:
    """Nemotron 3 Ultra: 3-5 practical tips from numbers calculated in code.

    Tries Ultra on the main address, then Ultra on its own region, then falls back to Super,
    so the owner always gets advice. Returns {"headline", "tips", "model_used"}."""
    if MOCK:
        return {"headline": f"(mock) Advice for {period}",
                "tips": [{"title": "Promote your best seller", "detail": "(mock) Your top product earns the most profit.",
                          "based_on": "products"}],
                "model_used": "mock"}
    system = load_prompt("advice.txt").format(
        period=period, language_instruction=LANG_INSTRUCTIONS.get(language, LANG_INSTRUCTIONS["english"]))
    data = json.dumps(insights, ensure_ascii=False)
    attempts = [(ULTRA, None, True), (ULTRA, ULTRA_BASE_URL, True), (SUPER, None, False)]
    last_err = None
    for model, url, think in attempts:
        try:
            raw = chat(model, system, data, temperature=0.3, max_tokens=2500 if think else 1200,
                       thinking=think, base_url=url, retries=1, timeout=120)
            return dict(_clean_advice(extract_json(raw)), model_used=model)
        except (RuntimeError, ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise RuntimeError(f"Advice failed on all models: {last_err}")


# ---------------------------------------------------------------- mock (no key)
def mock_classify(message: str) -> dict:
    m = message.lower()
    if re.search(r"[؀-ۿ]", message):
        lang = "mixed" if re.search(r"[a-z]{3,}", m) else "urdu"
    elif re.search(r"\b(hai|hain|kya|kitne|kitna|chahiye|dein|kar|karein|mein|ka|ki|ke|nahi|kal|parson|bhai|ji|haan|aur|na|mera|meri|tum|ho|thora|baje|assalam|alaikum|salam|shukriya)\b", m):
        lang = "roman_urdu"
    else:
        lang = "english"
    if re.search(r"\b(idiot|stupid|bakwas|ullu|gadha|kamina|shut up)\b", m):
        intent = "abuse"
    elif re.search(r"\b(late|kharab|ganda|worst|refund|complain|complaint|ghalat|wrong)\b", m):
        intent = "complaint"
    elif re.search(r"kam kar|discount|last price|sasta|\bless\b", m):
        intent = "bargain"
    elif re.search(r"chahiye|order|want|bhej|need|\bconfirm\b|\bhaan\b", m):
        intent = "order"
    elif re.search(r"book|appointment|fitting|slot", m):
        intent = "booking"
    elif re.search(r"^(hi|hello|salam|assalam|aoa)\b", m):
        intent = "greeting"
    else:
        intent = "faq"
    return {"language": lang, "intent": intent, "urgent": intent == "complaint" and "!" in m}
