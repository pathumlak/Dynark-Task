"""The owner's page (part 2). Standard library only, no install needed.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date
"""

import os
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from plan import build_plan, read_json

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "../data")
TODAY = os.environ.get("TODAY") or date.today().isoformat()

REASONS = {
    "duplicate_id": "Another invoice uses the same number, so we can't tell which is right.",
    "invalid_amount": "The amount is missing, not a number, or not above zero.",
    "missing_due_date": "The invoice has no due date.",
    "invalid_due_date": "The due date is not a real date (it should look like 2026-09-30).",
    "invalid_paid_date": "The paid date is not a real date, or it is in the future.",
}
STEP_LABEL = {"friendly": "Friendly reminder", "firm": "Firm reminder", "final": "Final notice"}

# invoice_id -> "approved" / "rejected" (kept while the app runs)
decisions = {}

CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0;padding:1rem;max-width:56rem;margin-inline:auto;
line-height:1.45;color:#1a1a1a;background:#fafafa}
h1{font-size:1.5rem;margin:.2rem 0}h2{font-size:1.2rem;margin-top:2rem}
.card{background:#fff;border:1px solid #d0d0d0;border-radius:8px;padding:1rem;margin:.8rem 0}
.meta{display:flex;flex-wrap:wrap;gap:.3rem 1rem;color:#444}
.step{display:inline-block;padding:.1rem .5rem;border-radius:4px;background:#e8eefc;font-weight:600}
pre{white-space:pre-wrap;word-wrap:break-word;background:#f3f3f3;padding:.7rem;border-radius:6px;
font-family:inherit;margin:.7rem 0}
button{font:inherit;padding:.6rem 1.1rem;border-radius:6px;border:1px solid #444;background:#fff;
cursor:pointer;min-height:44px}
button.ok{background:#1b6e2b;color:#fff;border-color:#1b6e2b}
button.no{background:#fff;color:#a01818;border-color:#a01818}
button:focus-visible{outline:3px solid #1a56db;outline-offset:2px}
form{display:inline-block;margin-right:.5rem}
.notice{padding:1rem;border-radius:8px;background:#eef6ee;border:1px solid #9bc59b}
.error{background:#fdeeee;border-color:#d99}
.approved{color:#1b6e2b;font-weight:600}.rejected{color:#a01818;font-weight:600}
"""


def load():
    """Return (plan, invoices_by_id, error_message)."""
    try:
        invoices = read_json(os.path.join(DATA_DIR, "invoices.json"))
        sent = read_json(os.path.join(DATA_DIR, "sent.json"))
        if not isinstance(invoices, list) or not isinstance(sent, list):
            raise ValueError("both files must contain a JSON list")
        plan = build_plan(invoices, sent, TODAY)
    except (OSError, ValueError) as e:
        return None, {}, str(e)
    by_id = {i["id"]: i for i in invoices if isinstance(i, dict) and isinstance(i.get("id"), str)}
    return plan, by_id, None


def render_action(a, by_id):
    inv = by_id.get(a["invoice_id"], {})
    amount = f"{inv.get('currency', '')} {inv.get('amount', 0):,.2f}"
    iid = escape(a["invoice_id"])
    if a["needs_approval"]:
        state = decisions.get(a["invoice_id"])
        if state:
            ctrl = (f'<p class="{state}">You {state} this reminder.</p>')
        else:
            ctrl = (
                f'<p>This reminder needs your approval.</p>'
                f'<form method="post" action="/decision"><input type="hidden" name="invoice_id" value="{iid}">'
                f'<button class="ok" name="decision" value="approved">Approve {iid}</button></form>'
                f'<form method="post" action="/decision"><input type="hidden" name="invoice_id" value="{iid}">'
                f'<button class="no" name="decision" value="rejected">Reject {iid}</button></form>'
            )
    else:
        ctrl = "<p>No approval needed.</p>"
    return (
        f'<article class="card"><h3>{escape(str(inv.get("customer", "")))} &middot; {iid}</h3>'
        f'<div class="meta"><span>{escape(amount)}</span>'
        f'<span>{a["days_overdue"]} days overdue</span>'
        f'<span class="step">{STEP_LABEL[a["step"]]}</span></div>'
        f'<pre>{escape(a["message"])}</pre>{ctrl}</article>'
    )


def render_page():
    plan, by_id, err = load()
    if err:
        body = (f'<div class="notice error" role="alert"><strong>We could not read the data.</strong>'
                f'<br>Check that the data folder ({escape(DATA_DIR)}) has valid invoices.json and '
                f'sent.json files.<br><small>{escape(err)}</small></div>')
    else:
        if plan["actions"]:
            acts = "".join(render_action(a, by_id) for a in plan["actions"])
        else:
            acts = '<div class="notice">Nothing to do today. No reminders are due.</div>'
        body = f"<h2>Today's reminders</h2>{acts}"
        if plan["skipped"]:
            items = "".join(
                f'<li><strong>{escape(s["invoice_id"])}</strong> '
                f'({escape(str(by_id.get(s["invoice_id"], {}).get("customer", "")))}): '
                f'{escape(REASONS.get(s["reason"], s["reason"]))}</li>'
                for s in plan["skipped"]
            )
            body += (f"<h2>Invoices we could not check</h2><p>Please fix the data for these "
                     f"invoices.</p><ul>{items}</ul>")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Payment reminders</title><style>{CSS}</style></head><body><main>"
        f"<h1>Payment reminders</h1><p>Plan for {escape(TODAY)}</p>{body}</main></body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        data = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/decision":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        iid = (form.get("invoice_id") or [""])[0]
        choice = (form.get("decision") or [""])[0]
        plan, _, _ = load()
        allowed = {a["invoice_id"] for a in plan["actions"] if a["needs_approval"]} if plan else set()
        if choice in ("approved", "rejected") and iid in allowed:
            decisions[iid] = choice
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main():
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()