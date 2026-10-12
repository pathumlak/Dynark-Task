# Payment reminder assistant

Python 3.11+, standard library only. Run everything from inside `python/`.

## Run
- Tests: `cd python && python -m unittest`
- Plan: `cd python && python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json`
- Page: `cd python && python app.py`, then open http://localhost:8000/ (env: `PORT`, `DATA_DIR`, `TODAY`)

## Decisions
- All rules live in `plan.py`; the page imports `build_plan`, it has no copy of the rules.
- Dates must be strictly `YYYY-MM-DD` (regex plus `date.fromisoformat`), so `2026-9-3` is invalid.
- Booleans, strings, NaN and amounts of 0 or less are invalid amounts.
- Invoices whose `id` is missing or not text are ignored, as they cannot be listed in the output.
- Messages come from templates: no AI, no key, no internet. They hold only the invoice facts.
- I did not add the owner's 25 EUR fee or the ECB rate; `RESEARCH.md` shows the sources do not support them.
- Approve/reject decisions are kept in memory only. The POST route accepts only invoices that need approval.

## Next, with more time
- Save decisions to disk and add a real email sender.
- Page tests, and currency-aware formatting.
- Optional AI-written messages, checked against the message rules before use.
