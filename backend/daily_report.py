"""Nightly owner report: a background job (bonus: runs as a Nebius Serverless Job).

What it does, once a day (e.g. 11 pm Karachi):
  1. Calculates today's sales, profit, orders and cancellations in Python.
  2. Nemotron 3 Nano writes a 2-3 sentence note about them.
  3. Saves the report (collection "reports") and, if Twilio + OWNER_WHATSAPP are set,
     sends it to the owner's own WhatsApp.

Run it on your laptop:            python daily_report.py            (or: python daily_report.py 2026-10-21)
Run it from the dashboard / API:  POST /admin/run-daily-report
Run it on Nebius Serverless Jobs: see "Bonus: Nebius Serverless" in the README.
It needs Firestore (FIREBASE_CREDENTIALS) to see the server's orders when it runs on its own.
"""
import os
import sys

import db
import summary


def format_report(r: dict, shop_name: str) -> str:
    lines = [f"📊 {shop_name}: report for {r['date']}",
             f"Orders: {r.get('orders', 0)} · Cancelled: {r.get('cancelled', 0)}",
             f"Sales: Rs {r.get('sales', 0):,} · Profit: Rs {r.get('profit', 0):,}"]
    change = r.get("sales_change_percent_vs_yesterday")
    if change is not None:
        lines.append(f"vs yesterday: {'+' if change > 0 else ''}{change}%")
    open_flags = len(db.list_flags())
    if open_flags:
        lines.append(f"🚨 {open_flags} alert(s) waiting in the dashboard")
    if r.get("note"):
        lines.append("")
        lines.append(r["note"])
    return "\n".join(lines)


def send_to_owner(text: str) -> bool:
    """WhatsApp the owner (only if Twilio and OWNER_WHATSAPP, e.g. +923001234567, are set)."""
    owner = os.getenv("OWNER_WHATSAPP", "").strip()
    sid, token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    if not (owner.startswith("+") and sid and token):
        return False
    from twilio.rest import Client

    try:
        Client(sid, token).messages.create(from_=os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
                                           to=f"whatsapp:{owner}", body=text)
        return True
    except Exception as e:  # a failed message must not fail the job
        print(f"WhatsApp to owner failed: {e}")
        return False


def run(day: str | None = None, language: str = "roman_urdu") -> dict:
    day = day or db.today_key()
    r = summary.daily(day, language)
    text = format_report(r, db.get_shop().get("name", "Your shop"))
    sent = send_to_owner(text)
    report = {"date": day, "numbers": {k: r.get(k) for k in ("orders", "cancelled", "sales", "profit")},
              "note": r.get("note", ""), "text": text, "sent_to_whatsapp": sent, "created_at": db.now_iso()}
    db.store.set("reports", day, report)
    return report


if __name__ == "__main__":
    result = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(result["text"])
    print(f"\nSaved to '{'Firestore' if db.USING_FIRESTORE else 'memory (lost when this script ends)'}'. "
          f"Sent to WhatsApp: {result['sent_to_whatsapp']}")
