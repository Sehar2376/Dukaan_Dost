"""Load DEMO data: the bakery + 20 customers + ~3 months of orders (some cancelled, some risky).

    cd backend
    python ../sample_data/load_sample.py

Uses FIREBASE_CREDENTIALS from backend/.env (Firestore) or memory if empty.
All names and numbers are made up and labelled demo data.
"""
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import db  # noqa: E402
from risk import score_cod_order  # noqa: E402

random.seed(7)
NAMES = ["Ayesha", "Bilal", "Hina", "Usman", "Fatima", "Ali", "Sana", "Hamza", "Maryam", "Zain",
         "Iqra", "Saad", "Mahnoor", "Danish", "Rabia", "Faraz", "Zoya", "Taha", "Amna", "Junaid"]
GOOD_ADDR = ["House 12, Street 5, Block 13-D, near Masjid, Gulshan-e-Iqbal",
             "Flat 304, Rufi Lake Drive, opposite park, Gulistan-e-Johar",
             "House 44, Khayaban-e-Ittehad, near Phase 6 market, DHA",
             "Plot 9, Block 2, Street 3, near Bahadurabad chowrangi, PECHS",
             "Apartment 7B, Clifton Block 5, beside Dolmen Mall, Clifton"]
VAGUE_ADDR = ["Gulshan", "DHA", "Johar mor ke paas"]


def main(days: int = 90):
    db.load_sample_shop(force=True)
    for col in ("orders", "customers", "flags", "bookings", "conversations"):
        db.store.delete_all(col)
    products = [p for p in db.get_products() if p.get("in_stock", True)]
    shop = db.get_shop()

    customers = {}
    for i, name in enumerate(NAMES):
        phone = f"0300{1000000 + i * 37311:07d}"[:11]
        customers[phone] = {"name": name, "addresses": [random.choice(GOOD_ADDR)],
                            "total_orders": 0, "completed_orders": 0, "cancelled_orders": 0,
                            "last_order_id": None, "flaky": i in (3, 11, 17)}  # 3 customers cancel a lot

    start = date.today() - timedelta(days=days)
    count = 0
    for d in range(days + 1):
        day = start + timedelta(days=d)
        n = random.randint(2, 5) + (2 if day.weekday() >= 5 else 0)  # busier weekends
        for _ in range(n):
            phone = random.choice(list(customers))
            c = customers[phone]
            picks = random.sample(products, k=random.choice([1, 1, 2]))
            items, subtotal, cost = [], 0, 0
            for p in picks:
                qty = random.choice([1, 1, 1, 2])
                items.append({"product_id": p["id"], "name": p["name"], "quantity": qty, "unit_price": p["price"],
                              "original_unit_price": p["price"], "discount_percent": 0,
                              "line_total": p["price"] * qty, "line_cost": p["cost_price"] * qty})
                subtotal += p["price"] * qty
                cost += p["cost_price"] * qty
            discount = round(subtotal * random.choice([0, 0, 0, 0.05]))
            address = random.choice(VAGUE_ADDR) if c["flaky"] and random.random() < 0.5 else c["addresses"][0]
            total = subtotal - discount + shop["delivery_fee"]
            payment = random.choice(["cod", "cod", "cod", "jazzcash", "easypaisa"])
            risk = score_cod_order(address, total, c["cancelled_orders"], c["completed_orders"]) if payment == "cod" \
                else {"level": "low", "reasons": ["Paid in advance"]}
            cancelled = random.random() < (0.45 if c["flaky"] else 0.04)
            recent = (date.today() - day).days <= 1
            status = "new" if recent else ("cancelled" if cancelled else "delivered")
            created = datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=random.randint(5, 16))
            oid = db.save_order({
                "customer_phone": phone, "customer_name": c["name"], "items": items, "subtotal": subtotal,
                "discount": discount, "delivery_fee": shop["delivery_fee"], "total": total, "cost_total": cost,
                "profit": subtotal - discount - cost, "address": address, "delivery_time": day.isoformat() + " 18:00",
                "payment_type": payment, "status": status, "risk_level": risk["level"],
                "risk_reasons": risk["reasons"], "created_at": created.isoformat(), "demo_data": True})
            c["total_orders"] += 1
            c["last_order_id"] = oid
            if status == "delivered":
                c["completed_orders"] += 1
            elif status == "cancelled":
                c["cancelled_orders"] += 1
            if status == "new" and risk["level"] == "high":
                db.add_flag("high_risk", phone, "; ".join(risk["reasons"]), oid)
            count += 1

    for phone, c in customers.items():
        c.pop("flaky")
        db.upsert_customer(phone, c)
    print(f"Loaded demo shop, {len(customers)} customers, {count} orders "
          f"({'Firestore' if db.USING_FIRESTORE else 'memory only - set FIREBASE_CREDENTIALS to keep it'}).")


if __name__ == "__main__":
    main()
