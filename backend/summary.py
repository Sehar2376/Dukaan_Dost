"""Daily and monthly numbers (F8). All math in Python; Nemotron only writes the short note.

`insights()` adds a deeper monthly breakdown that Nemotron 3 Ultra turns into business advice."""
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

import ai
import db


def _orders_between(start: str, end: str) -> list[dict]:
    """Orders whose created_at date is in [start, end] (YYYY-MM-DD strings)."""
    return [o for o in db.list_orders() if start <= db.local_date(o.get("created_at", "")) <= end]


def compute(orders: list[dict]) -> dict:
    done = [o for o in orders if o.get("status") != "cancelled"]
    top = Counter()
    for o in done:
        for it in o["items"]:
            top[it["name"]] += it["quantity"]
    return {
        "orders": len(done),
        "cancelled": len(orders) - len(done),
        "sales": sum(o["total"] - o.get("delivery_fee", 0) for o in done),
        "profit": sum(o.get("profit", 0) for o in done),
        "average_order": round(sum(o["total"] for o in done) / len(done)) if done else 0,
        "high_risk_orders": sum(1 for o in orders if o.get("risk_level") == "high"),
        "top_products": [{"name": n, "quantity": q} for n, q in top.most_common(3)],
    }


def _change(now: int, before: int):
    return None if not before else round((now - before) / before * 100)


def daily(day: str | None = None, language: str = "roman_urdu") -> dict:
    day = day or db.now_karachi().date().isoformat()
    prev = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    numbers = compute(_orders_between(day, day))
    numbers["sales_change_percent_vs_yesterday"] = _change(numbers["sales"], compute(_orders_between(prev, prev))["sales"])
    return {"date": day, **numbers, "note": _safe_note(numbers, f"the day {day}", language)}


def monthly(month: str | None = None, language: str = "roman_urdu") -> dict:
    month = month or db.now_karachi().strftime("%Y-%m")
    first = date.fromisoformat(month + "-01")
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = (nxt - timedelta(days=1)).isoformat()
    prev_first = (first - timedelta(days=1)).replace(day=1)
    orders = _orders_between(first.isoformat(), last)
    numbers = compute(orders)
    numbers["sales_change_percent_vs_last_month"] = _change(
        numbers["sales"], compute(_orders_between(prev_first.isoformat(), (first - timedelta(days=1)).isoformat()))["sales"])

    per_day = defaultdict(lambda: {"sales": 0, "profit": 0, "orders": 0})
    for o in orders:
        if o.get("status") == "cancelled":
            continue
        d = per_day[db.local_date(o["created_at"])]
        d["sales"] += o["total"] - o.get("delivery_fee", 0)
        d["profit"] += o.get("profit", 0)
        d["orders"] += 1
    chart = []
    cur = first
    while cur < nxt:  # every day of the month, zeros included, for the bar chart
        chart.append({"date": cur.isoformat(), **per_day.get(cur.isoformat(), {"sales": 0, "profit": 0, "orders": 0})})
        cur += timedelta(days=1)
    return {"month": month, **numbers, "daily_chart": chart,
            "note": _safe_note(numbers, f"the month {month}", language)}


def _safe_note(numbers: dict, period: str, language: str) -> str:
    if numbers["orders"] == 0 and numbers["cancelled"] == 0:
        return "Is period mein koi order nahi." if language != "english" else "No orders in this period."
    try:
        return ai.summary_note(numbers, period, language)
    except RuntimeError:
        return ""


# ------------------------------------------------------------------ deeper monthly numbers for Ultra advice
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _month_range(month: str) -> tuple[str, str, str]:
    """(first day, last day, previous month 'YYYY-MM')."""
    first = date.fromisoformat(month + "-01")
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev = (first - timedelta(days=1)).strftime("%Y-%m")
    return first.isoformat(), (nxt - timedelta(days=1)).isoformat(), prev


def _area(address: str, areas: list[str]) -> str:
    a = (address or "").lower()
    for area in areas:
        if any(k in a for k in re.split(r"[\s\-]+", area.lower()) if len(k) >= 3):
            return area
    return "other"


def insights(month: str | None = None) -> dict:
    """Everything the advisor needs, calculated exactly in code (the AI never adds numbers up)."""
    month = month or db.now_karachi().strftime("%Y-%m")
    start, end, prev = _month_range(month)
    orders = _orders_between(start, end)
    done = [o for o in orders if o.get("status") != "cancelled"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    areas = db.get_shop().get("delivery_areas", [])

    products = defaultdict(lambda: {"quantity": 0, "sales": 0, "profit": 0, "discount_given": 0})
    for o in done:
        for it in o["items"]:
            p = products[it["name"]]
            p["quantity"] += it["quantity"]
            p["sales"] += it["line_total"]
            p["profit"] += it["line_total"] - it.get("line_cost", 0)
            p["discount_given"] += (it.get("original_unit_price", it["unit_price"]) - it["unit_price"]) * it["quantity"]
    for p in products.values():
        p["margin_percent"] = round(p["profit"] / p["sales"] * 100) if p["sales"] else 0

    weekdays = {d: {"orders": 0, "sales": 0} for d in WEEKDAYS}
    for o in done:
        w = WEEKDAYS[date.fromisoformat(db.local_date(o["created_at"])).weekday()]
        weekdays[w]["orders"] += 1
        weekdays[w]["sales"] += o["total"] - o.get("delivery_fee", 0)

    def rate_by(key_fn):
        out = defaultdict(lambda: {"orders": 0, "cancelled": 0})
        for o in orders:
            k = key_fn(o)
            out[k]["orders"] += 1
            out[k]["cancelled"] += o.get("status") == "cancelled"
        for v in out.values():
            v["cancel_rate_percent"] = round(v["cancelled"] / v["orders"] * 100) if v["orders"] else 0
        return dict(out)

    high = [o for o in orders if o.get("risk_level") == "high"]
    per_customer = Counter(o["customer_phone"] for o in done)
    base = compute(orders)
    prev_sales = monthly_sales(prev)
    today = db.now_karachi().date()
    first_day, last_day = date.fromisoformat(start), date.fromisoformat(end)
    partial = first_day <= today < last_day
    days_counted = (today - first_day).days + 1 if partial else (last_day - first_day).days + 1
    prev_days = (first_day - date.fromisoformat(prev + "-01")).days
    return {
        "month": month,
        "month_not_finished": partial,
        "days_counted": days_counted,
        "days_in_month": (last_day - first_day).days + 1,
        "demo_data": any(o.get("demo_data") for o in orders),
        "totals": {**{k: base[k] for k in ("orders", "cancelled", "sales", "profit", "average_order")},
                   "profit_margin_percent": round(base["profit"] / base["sales"] * 100) if base["sales"] else 0,
                   "sales_last_month": prev_sales,
                   "sales_change_percent_vs_last_month": None if partial else _change(base["sales"], prev_sales),
                   "sales_per_day": round(base["sales"] / days_counted),
                   "sales_per_day_last_month": round(prev_sales / prev_days) if prev_days else 0,
                   "sales_per_day_change_percent": _change(round(base["sales"] / days_counted),
                                                           round(prev_sales / prev_days) if prev_days else 0)},
        "products": dict(sorted(products.items(), key=lambda kv: -kv[1]["profit"])),
        "weekdays": weekdays,
        "cancellations": {
            "rate_percent": round(len(cancelled) / len(orders) * 100) if orders else 0,
            "lost_sales": sum(o["total"] - o.get("delivery_fee", 0) for o in cancelled),
            "by_payment_type": rate_by(lambda o: o.get("payment_type", "unknown")),
            "by_area": rate_by(lambda o: _area(o.get("address", ""), areas)),
        },
        "risk": {"high_risk_orders": len(high),
                 "high_risk_later_cancelled": sum(1 for o in high if o.get("status") == "cancelled")},
        "discounts": {"orders_with_discount": sum(1 for o in done if o.get("discount", 0) > 0),
                      "total_discount_given": sum(o.get("discount", 0) for o in done)},
        "customers": {"unique": len(per_customer),
                      "repeat_customers": sum(1 for n in per_customer.values() if n > 1),
                      "orders_from_repeat_customers": sum(n for n in per_customer.values() if n > 1)},
    }


def monthly_sales(month: str) -> int:
    start, end, _ = _month_range(month)
    return compute(_orders_between(start, end))["sales"]
