"""Market price check (bonus feature F9): "What do other shops charge for this?"

1. Tavily searches the web for the product's price in the shop's city.
2. Nemotron 3 Super reads the search results and pulls out the prices it finds.
3. Python (not the AI) compares them with the owner's price: low / typical / high and a verdict.

No Tavily key?  -> clearly labelled SAMPLE search results are used (no internet call, $0).
No Nebius key?  -> prices are read from the results with a simple pattern instead of Super.
Results are saved for 24 hours, so opening the page again costs nothing.
"""
import json
import os
import re
import statistics
from datetime import datetime, timedelta, timezone

import httpx

import ai
import db

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_READY = bool(TAVILY_KEY)
TAVILY_DAILY_LIMIT = int(os.getenv("TAVILY_DAILY_LIMIT", "30"))  # searches per day (free plan: 1,000/month)
CACHE_HOURS = 24


class MarketError(Exception):
    """A problem the owner should see as a friendly message (limit reached, search failed...)."""


# ---------------------------------------------------------------- step 1: web search (Tavily)
def build_query(product_name: str, city: str) -> str:
    return f"{product_name} price in {city or 'Pakistan'} Rs"


def tavily_search(query: str, max_results: int = 6) -> list[dict]:
    """One basic Tavily search (1 credit). Returns [{title, url, content}]."""
    if db.get_usage().get("tavily_calls", 0) >= TAVILY_DAILY_LIMIT:
        raise MarketError(f"Today's limit of {TAVILY_DAILY_LIMIT} market searches is reached. Try again tomorrow.")
    try:
        r = httpx.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {TAVILY_KEY}"},
            json={"query": query, "search_depth": "basic", "topic": "general", "country": "pakistan",
                  "max_results": max_results, "include_answer": False},
            timeout=30,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise MarketError(f"Web search failed ({e.__class__.__name__}). Check TAVILY_API_KEY or try again.") from e
    db.add_usage({"tavily_calls": 1})
    return [{"title": x.get("title", "")[:200], "url": x.get("url", ""), "content": (x.get("content") or "")[:1200]}
            for x in r.json().get("results", [])]


def sample_results(product_name: str, price: float, city: str) -> list[dict]:
    """Fake but realistic search results, used only when there is no Tavily key. Clearly labelled."""
    p = max(price, 100)
    shops = [("Sample Bakers", 0.9), ("Demo Sweets & Cakes", 1.05), ("Example Home Kitchen", 1.15),
             ("Test Cake Studio", 0.95)]
    return [{"title": f"{name} - {product_name} (SAMPLE result, no Tavily key)",
             "url": f"https://example.com/sample-{i + 1}",
             "content": f"{product_name} available in {city or 'Karachi'}. Price Rs {round(p * f / 10) * 10:,}. "
                        f"Free delivery in nearby areas. (sample data)"}
            for i, (name, f) in enumerate(shops)]


# ---------------------------------------------------------------- step 2: read prices (Nemotron Super)
PRICE_RE = re.compile(r"(?:rs\.?|pkr|₨)\s*([\d,]{2,9})", re.I)


def regex_prices(results: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(results):
        for m in PRICE_RE.finditer(r["content"]):
            before = r["content"][max(0, m.start() - 25):m.start()].lower()
            if re.search(r"above|over|minimum|min\.|delivery|save|off", before):
                continue  # "free delivery above Rs 3,000", "save Rs 200": not a product price
            out.append({"price": float(m.group(1).replace(",", "")), "source": i, "what": r["title"][:80]})
    return out


def read_prices(product_name: str, results: list[dict], language: str) -> tuple[list[dict], str, str]:
    """Returns (prices, short note for the owner, model used)."""
    if ai.MOCK or not results:
        return regex_prices(results), "(mock) Prices were read from the search results with a simple pattern.", "pattern"
    system = ai.load_prompt("market.txt").format(
        product=product_name, language_instruction=ai.LANG_INSTRUCTIONS.get(language, ai.LANG_INSTRUCTIONS["english"]))
    numbered = "\n\n".join(f"[{i}] {r['title']}\n{r['url']}\n{r['content']}" for i, r in enumerate(results))
    try:
        raw = ai.chat(ai.SUPER, system, numbered, temperature=0, max_tokens=900)
        data = ai.extract_json(raw)
        prices = []
        for p in data.get("prices", [])[:20]:
            try:
                prices.append({"price": float(str(p["price"]).replace(",", "")), "source": int(p.get("source", 0)),
                               "what": str(p.get("what", ""))[:120]})
            except (KeyError, ValueError, TypeError):
                continue
        return prices, str(data.get("note", ""))[:400], ai.SUPER
    except (RuntimeError, ValueError, json.JSONDecodeError):
        return regex_prices(results), "AI could not read the results; prices were found with a simple pattern.", "pattern"


# ---------------------------------------------------------------- step 3: compare (pure Python)
def compare(my_price: float, prices: list[dict]) -> dict:
    """Keep believable prices (30%-300% of the owner's price) and compare. All maths here, not in the AI."""
    good = sorted(p["price"] for p in prices if my_price * 0.3 <= p["price"] <= my_price * 3)
    if len(good) < 2:
        return {"found": len(good), "verdict": "not_enough_data",
                "message": "Not enough prices found online to compare. Try a simpler product name."}
    typical = statistics.median(good)
    diff = round((my_price - typical) / typical * 100)
    if diff > 10:
        verdict, msg = "higher", f"Your price is {diff}% above the typical market price."
    elif diff < -10:
        verdict, msg = "lower", f"Your price is {abs(diff)}% below the typical market price. You may be able to charge more."
    else:
        verdict, msg = "similar", "Your price is close to the typical market price."
    return {"found": len(good), "low": min(good), "typical": round(typical), "high": max(good),
            "your_price": my_price, "difference_percent": diff, "verdict": verdict, "message": msg}


# ---------------------------------------------------------------- the whole check
def _fresh(saved: dict) -> bool:
    try:
        t = datetime.fromisoformat(saved["checked_at"])
        return datetime.now(timezone.utc) - t.astimezone(timezone.utc) < timedelta(hours=CACHE_HOURS)
    except (KeyError, ValueError):
        return False


def check(product_id: str, language: str = "english", refresh: bool = False) -> dict:
    product = db.get_product(product_id)
    if not product:
        raise MarketError("Product not found.")
    saved = db.store.get("market", product_id)
    if saved and not refresh and _fresh(saved):
        return {**saved, "cached": True}
    if not ai.MOCK and ai.over_budget():
        raise MarketError("Daily AI budget reached. Try again tomorrow.")

    shop = db.get_shop()
    query = build_query(product["name"], shop.get("city", "Karachi"))
    results = tavily_search(query) if TAVILY_READY else sample_results(product["name"], product["price"], shop.get("city", ""))
    prices, note, model = read_prices(product["name"], results, language)
    result = {
        "product_id": product_id, "product": product["name"], "query": query,
        "search": "tavily" if TAVILY_READY else "sample (no TAVILY_API_KEY)",
        "model_used": model, "note": note,
        **compare(float(product["price"]), prices),
        "prices": prices,
        "sources": [{"title": r["title"], "url": r["url"]} for r in results],
        "checked_at": db.now_iso(),
    }
    db.store.set("market", product_id, result)
    return {**result, "cached": False}


def saved_checks() -> list[dict]:
    """Latest saved checks (used by the dashboard and by the Ultra advisor)."""
    return sorted(db.store.all("market"), key=lambda c: c.get("checked_at", ""), reverse=True)


def for_advice() -> list[dict]:
    """Short version of saved checks for the monthly advice (only real comparisons)."""
    return [{"product": c["product"], "your_price": c.get("your_price"), "market_typical": c.get("typical"),
             "market_low": c.get("low"), "market_high": c.get("high"),
             "difference_percent": c.get("difference_percent"), "sample_data": not c["search"].startswith("tavily")}
            for c in saved_checks() if c.get("verdict") in ("higher", "lower", "similar")]
