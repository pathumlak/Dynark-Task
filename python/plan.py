"""Payment reminder rules engine (part 1).

Run from inside python/:

    python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json

This starter only reads the files and writes an empty plan in the required shape.
The rules are yours to build.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import date

DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
STEPS = ["friendly", "firm", "final"]  # lowest to highest
THRESHOLDS = [("final", 24), ("firm", 10), ("friendly", 3)]  # highest first
NEEDS_APPROVAL = {"friendly": False, "firm": True, "final": True}


def parse_date(value):
    """Return a date for a strict YYYY-MM-DD string, otherwise None."""
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def valid_amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0


def skip_reason(inv, today, duplicate_ids):
    """First bad-data reason for an invoice, or None if the data is fine."""
    if inv["id"] in duplicate_ids:
        return "duplicate_id"
    if not valid_amount(inv.get("amount")):
        return "invalid_amount"
    due = inv.get("due_date")
    if due is None or due == "":
        return "missing_due_date"
    if parse_date(due) is None:
        return "invalid_due_date"
    paid = inv.get("paid_date")
    if paid is not None:
        paid_on = parse_date(paid)
        if paid_on is None or paid_on > today:
            return "invalid_paid_date"
    return None


def make_message(inv, step, days):
    name = inv.get("customer")
    ref = inv["id"]
    due = inv["due_date"]
    amount = f"{inv.get('currency')} {inv['amount']:,.2f}"
    unit = "day" if days == 1 else "days"
    facts = (
        f"Invoice {ref} for {amount} was due on {due} and is now {days} {unit} overdue."
    )
    if step == "friendly":
        return (
            f"Dear {name},\n\n"
            f"A friendly reminder: {facts} "
            "If you have already paid, please ignore this message. "
            "Otherwise we would be grateful if you could arrange payment.\n\n"
            "Kind regards"
        )
    if step == "firm":
        return (
            f"Dear {name},\n\n"
            f"{facts} We have not yet received payment. "
            "Please pay this invoice as soon as possible, or contact us "
            "if there is a problem we should know about.\n\n"
            "Regards"
        )
    return (
        f"Dear {name},\n\n"
        f"Final notice: {facts} "
        "We still have not received payment. "
        "Please pay this invoice immediately, or contact us today to discuss it.\n\n"
        "Regards"
    )


def build_plan(invoices, sent, today):
    """Return the plan for `today` as a dict with the keys today, actions and skipped.

    Raises ValueError if `today` is not a real YYYY-MM-DD date.
    """
    today_date = parse_date(today)
    if today_date is None:
        raise ValueError(f"today must be a real date as YYYY-MM-DD, got {today!r}")

    invoices = [i for i in invoices if isinstance(i, dict) and isinstance(i.get("id"), str)]
    counts = Counter(i["id"] for i in invoices)
    duplicate_ids = {k for k, n in counts.items() if n > 1}

    # highest step already sent per invoice id (index in STEPS)
    highest_sent = {}
    for s in sent if isinstance(sent, list) else []:
        if not isinstance(s, dict):
            continue
        inv_id, step = s.get("invoice_id"), s.get("step")
        if isinstance(inv_id, str) and step in STEPS:
            highest_sent[inv_id] = max(highest_sent.get(inv_id, -1), STEPS.index(step))

    actions, skipped = [], []
    for inv in invoices:
        reason = skip_reason(inv, today_date, duplicate_ids)
        if reason:
            if reason != "duplicate_id" or not any(
                s["invoice_id"] == inv["id"] for s in skipped
            ):
                skipped.append({"invoice_id": inv["id"], "reason": reason})
            continue
        if inv.get("paid_date") is not None:
            continue
        days = (today_date - parse_date(inv["due_date"])).days
        step = next((name for name, limit in THRESHOLDS if days >= limit), None)
        if step is None:
            continue
        if highest_sent.get(inv["id"], -1) >= STEPS.index(step):
            continue
        actions.append(
            {
                "invoice_id": inv["id"],
                "step": step,
                "needs_approval": NEEDS_APPROVAL[step],
                "days_overdue": days,
                "message": make_message(inv, step, days),
            }
        )

    actions.sort(key=lambda a: a["invoice_id"])
    skipped.sort(key=lambda s: s["invoice_id"])
    return {"today": today, "actions": actions, "skipped": skipped}


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Plan today's payment reminders.")
    parser.add_argument("--invoices", required=True, help="path to invoices.json")
    parser.add_argument("--sent", required=True, help="path to sent.json")
    parser.add_argument("--today", required=True, help="date as YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="path to write the plan JSON")
    args = parser.parse_args()

    if parse_date(args.today) is None:
        sys.exit(f"Error: --today must be a real date as YYYY-MM-DD, got {args.today!r}")
    try:
        invoices = read_json(args.invoices)
        sent = read_json(args.sent)
    except (OSError, ValueError) as e:
        sys.exit(f"Error: cannot read input file: {e}")
    if not isinstance(invoices, list) or not isinstance(sent, list):
        sys.exit("Error: invoices and sent files must each contain a JSON list")

    plan = build_plan(invoices, sent, args.today)
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")
    except OSError as e:
        sys.exit(f"Error: cannot write output file: {e}")


if __name__ == "__main__":
    main()
