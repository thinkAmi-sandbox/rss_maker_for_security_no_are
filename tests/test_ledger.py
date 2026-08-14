import unittest

from src.diff import FeedEntry
from src.ledger import (
    LedgerError,
    parse_ledger,
    plan_update,
    render_ledger,
)

SAMPLE = """p,guid,first_seen
491,http://www.tsujileaks.com/?p=491,2026-08-13
2351,https://www.tsujileaks.com/?p=2351,2026-08-13
"""


class ParseLedgerTest(unittest.TestCase):
    def test_roundtrip(self):
        entries = parse_ledger(SAMPLE)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[491].guid, "http://www.tsujileaks.com/?p=491")
        self.assertEqual(render_ledger(entries), SAMPLE)

    def test_empty_text_is_empty_ledger(self):
        self.assertEqual(parse_ledger(""), {})

    def test_bad_header_fails(self):
        with self.assertRaises(LedgerError):
            parse_ledger("a,b,c\n1,x,y\n")

    def test_non_numeric_p_fails(self):
        """手編集ミス等で p が数値でない場合、行を示した LedgerError になる。"""
        text = "p,guid,first_seen\nabc,http://www.tsujileaks.com/?p=1,2026-01-01\n"
        with self.assertRaises(LedgerError) as ctx:
            parse_ledger(text)
        self.assertIn("abc", str(ctx.exception))

    def test_duplicate_p_fails(self):
        text = "p,guid,first_seen\n1,g,2026-01-01\n1,g,2026-01-01\n"
        with self.assertRaises(LedgerError):
            parse_ledger(text)


class PlanUpdateTest(unittest.TestCase):
    def test_appends_unknown_only(self):
        entries = parse_ledger(SAMPLE)
        feed = [
            FeedEntry(491, "http://www.tsujileaks.com/?p=491"),  # 既知
            FeedEntry(2360, "https://www.tsujileaks.com/?p=2360"),  # 新規
        ]
        update = plan_update(entries, feed, today="2026-09-01")
        self.assertEqual(len(update.additions), 1)
        added = update.additions[0]
        self.assertEqual(added.article_number, 2360)
        self.assertEqual(added.first_seen, "2026-09-01")
        # 既存行は不変
        self.assertEqual(update.entries[491].first_seen, "2026-08-13")

    def test_idempotent_when_no_change(self):
        entries = parse_ledger(SAMPLE)
        feed = [FeedEntry(491, "http://www.tsujileaks.com/?p=491")]
        update = plan_update(entries, feed, today="2026-09-01")
        self.assertEqual(update.additions, [])
        self.assertEqual(render_ledger(update.entries), SAMPLE)

    def test_guid_drift_fails(self):
        """既知 p で guid 文字列が食い違ったら guid 不変の前提の崩れ。"""
        entries = parse_ledger(SAMPLE)
        feed = [FeedEntry(491, "https://www.tsujileaks.com/?p=491")]
        with self.assertRaises(LedgerError) as ctx:
            plan_update(entries, feed, today="2026-09-01")
        message = str(ctx.exception)
        self.assertIn("http://www.tsujileaks.com/?p=491", message)
        self.assertIn("https://www.tsujileaks.com/?p=491", message)

    def test_initial_creation_from_feed(self):
        feed = [
            FeedEntry(2351, "https://www.tsujileaks.com/?p=2351"),
            FeedEntry(491, "http://www.tsujileaks.com/?p=491"),
        ]
        update = plan_update({}, feed, today="2026-08-13")
        self.assertEqual(len(update.additions), 2)
        # p 昇順で書き出される
        self.assertEqual(render_ledger(update.entries), SAMPLE)


if __name__ == "__main__":
    unittest.main()
