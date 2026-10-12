"""Run from inside python/:  python -m unittest

This example only checks the shape of the output, so it passes on the starter.
Add your own tests for the rules.
"""

import re
import unittest

from plan import build_plan

TODAY = "2026-10-12"


def inv(id="INV-1", due="2026-10-01", **kw):
    d = {"id": id, "customer": "Acme Ltd", "email": "a@x.test", "amount": 100.0,
         "currency": "EUR", "due_date": due, "paid_date": None}
    d.update(kw)
    return d


def sent(id, step):
    return {"invoice_id": id, "step": step, "sent_on": "2026-10-01"}


def due_days_ago(n):
    from datetime import date, timedelta
    return (date.fromisoformat(TODAY) - timedelta(days=n)).isoformat()


class ShapeTest(unittest.TestCase):
    def test_empty_input_gives_empty_plan(self):
        self.assertEqual(build_plan([], [], TODAY),
                         {"today": TODAY, "actions": [], "skipped": []})

    def test_bad_today_raises(self):
        with self.assertRaises(ValueError):
            build_plan([], [], "2026-02-30")


class StepTest(unittest.TestCase):
    def step_for(self, days, sent_list=()):
        plan = build_plan([inv(due=due_days_ago(days))], list(sent_list), TODAY)
        return plan["actions"][0]["step"] if plan["actions"] else None

    def test_thresholds(self):
        for days, expected in [(0, None), (2, None), (3, "friendly"), (9, "friendly"),
                               (10, "firm"), (23, "firm"), (24, "final"), (100, "final")]:
            self.assertEqual(self.step_for(days), expected, f"{days} days")

    def test_approval_flags(self):
        for days, flag in [(3, False), (10, True), (24, True)]:
            a = build_plan([inv(due=due_days_ago(days))], [], TODAY)["actions"][0]
            self.assertEqual(a["needs_approval"], flag)

    def test_only_highest_step_planned(self):
        self.assertEqual(self.step_for(12), "firm")

    def test_same_step_already_sent(self):
        self.assertIsNone(self.step_for(12, [sent("INV-1", "firm")]))

    def test_higher_step_already_sent(self):
        self.assertIsNone(self.step_for(12, [sent("INV-1", "final")]))

    def test_lower_step_sent_still_plans_higher(self):
        self.assertEqual(self.step_for(12, [sent("INV-1", "friendly")]), "firm")

    def test_unknown_sent_entries_ignored(self):
        self.assertEqual(self.step_for(12, [sent("INV-1", "bogus"), sent("INV-9", "final")]), "firm")

    def test_days_overdue_value(self):
        a = build_plan([inv(due=due_days_ago(12))], [], TODAY)["actions"][0]
        self.assertEqual(a["days_overdue"], 12)


class PaidTest(unittest.TestCase):
    def test_paid_plans_nothing_even_with_sent(self):
        plan = build_plan([inv(due="2026-09-01", paid_date="2026-10-05")],
                          [sent("INV-1", "friendly")], TODAY)
        self.assertEqual((plan["actions"], plan["skipped"]), ([], []))

    def test_paid_today_is_ok(self):
        plan = build_plan([inv(due="2026-09-01", paid_date=TODAY)], [], TODAY)
        self.assertEqual((plan["actions"], plan["skipped"]), ([], []))

    def test_missing_paid_date_key_is_unpaid(self):
        i = inv(due="2026-09-01")
        del i["paid_date"]
        self.assertEqual(len(build_plan([i], [], TODAY)["actions"]), 1)


class SkipTest(unittest.TestCase):
    def reason(self, **kw):
        s = build_plan([inv(**kw)], [], TODAY)["skipped"]
        return s[0]["reason"] if s else None

    def test_invalid_amount(self):
        for bad in ["100", True, 0, -5, None]:
            self.assertEqual(self.reason(amount=bad), "invalid_amount", repr(bad))

    def test_missing_amount_key(self):
        i = inv()
        del i["amount"]
        self.assertEqual(build_plan([i], [], TODAY)["skipped"][0]["reason"], "invalid_amount")

    def test_missing_due_date(self):
        self.assertEqual(self.reason(due=None), "missing_due_date")
        self.assertEqual(self.reason(due=""), "missing_due_date")

    def test_invalid_due_date(self):
        for bad in ["2026-02-30", "30/09/2026", "2026-9-3", "abc", 20260930]:
            self.assertEqual(self.reason(due=bad), "invalid_due_date", repr(bad))

    def test_invalid_paid_date(self):
        for bad in ["", "2026-13-01", "2026-10-13", 5]:
            self.assertEqual(self.reason(paid_date=bad), "invalid_paid_date", repr(bad))

    def test_first_reason_wins(self):
        self.assertEqual(self.reason(amount=0, due=None), "invalid_amount")
        self.assertEqual(self.reason(due="bad", paid_date="bad"), "invalid_due_date")

    def test_duplicates_listed_once_and_both_skipped(self):
        plan = build_plan([inv("INV-5"), inv("INV-5", amount=-1), inv("INV-6")], [], TODAY)
        self.assertEqual(plan["skipped"], [{"invoice_id": "INV-5", "reason": "duplicate_id"}])
        self.assertEqual([a["invoice_id"] for a in plan["actions"]], ["INV-6"])

    def test_skipped_even_if_paid(self):
        self.assertEqual(self.reason(due="nope", paid_date="2026-10-01"), "invalid_due_date")


class SortTest(unittest.TestCase):
    def test_plain_text_order(self):
        ids = ["INV-99", "INV-100", "INV-1000"]
        plan = build_plan([inv(i) for i in ids], [], TODAY)
        self.assertEqual([a["invoice_id"] for a in plan["actions"]],
                         ["INV-100", "INV-1000", "INV-99"])


class MessageTest(unittest.TestCase):
    def test_message_content_and_no_extra_figures(self):
        for days in (3, 12, 30):
            a = build_plan([inv(due=due_days_ago(days), amount=1250.0)], [], TODAY)["actions"][0]
            m = a["message"]
            for needle in ["Acme Ltd", "INV-1", due_days_ago(days), "EUR 1,250.00", str(days)]:
                self.assertIn(needle, m)
            # remove the allowed figures, nothing numeric may remain
            rest = m.replace("INV-1", "").replace(due_days_ago(days), "")
            rest = rest.replace("EUR 1,250.00", "").replace(str(days), "")
            self.assertEqual(re.findall(r"\d", rest), [])


if __name__ == "__main__":
    unittest.main()