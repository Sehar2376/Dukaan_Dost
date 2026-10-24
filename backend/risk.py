"""COD fake-order risk score (F3). Pure Python rules - the AI never decides the score.

Points (from the project report, Section 8):
  Address missing block/house, street or landmark   +2
  Each past cancellation                            +2 (max +4)
  First-time customer with a large order            +2
  Order total far above usual order size (>2.5x)    +1
  Repeat customer with completed orders             -2
Level: 0-1 low, 2-3 medium, 4+ high
"""
import re

ADDRESS_PARTS = {
    "house/block": r"\b(house|h\s*#|h\.?no|flat|apt|apartment|plot|block|blk|phase|ghar|makan)\b|#\s*\d|\b\d+[-/]?[a-z]?\b",
    "street": r"\b(street|st|road|rd|lane|gali|avenue|ave|khayaban|commercial)\b",
    "landmark": r"\b(near|opposite|opp|behind|beside|samne|samnay|peeche|qareeb|nazdeek|pass)\b",
}


def missing_address_parts(address: str) -> list[str]:
    a = (address or "").lower()
    return [name for name, pattern in ADDRESS_PARTS.items() if not re.search(pattern, a)]


def score_cod_order(
    address: str,
    total: float,
    past_cancellations: int = 0,
    completed_orders: int = 0,
    large_order_threshold: float = 8000,
    usual_order_size: float = 2500,
) -> dict:
    points, reasons = 0, []

    missing = missing_address_parts(address)
    if missing:
        points += 2
        reasons.append(f"Address incomplete (missing {', '.join(missing)})")

    if past_cancellations > 0:
        pts = min(2 * past_cancellations, 4)
        points += pts
        reasons.append(f"{past_cancellations} past cancelled order(s)")

    is_new = completed_orders == 0 and past_cancellations == 0
    if is_new and total >= large_order_threshold:
        points += 2
        reasons.append(f"First-time customer with a large order (Rs {total:,.0f})")

    if usual_order_size and total > 2.5 * usual_order_size:
        points += 1
        reasons.append("Order much bigger than this shop's usual order")

    if completed_orders > 0:
        points -= 2
        reasons.append(f"Trusted repeat customer ({completed_orders} completed orders)")

    level = "high" if points >= 4 else "medium" if points >= 2 else "low"
    return {"level": level, "points": points, "reasons": reasons}
