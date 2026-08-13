import unittest

from src.guid import resolve_guid, synthesize_guid
from src.ledger import parse_ledger


class GuidTest(unittest.TestCase):
    def test_synthesize_is_http_www(self):
        """合成 guid は http・www あり(歴史的証拠に基づく推定)。"""
        for p in (10, 400, 426, 488):
            self.assertEqual(
                synthesize_guid(p), f"http://www.tsujileaks.com/?p={p}"
            )

    def test_ledger_value_wins_verbatim(self):
        """台帳の観測値は無加工で優先される(https のままでも書き換えない)。"""
        ledger = parse_ledger(
            "p,guid,first_seen\n"
            "2351,https://www.tsujileaks.com/?p=2351,2026-08-13\n"
        )
        self.assertEqual(
            resolve_guid(2351, ledger), "https://www.tsujileaks.com/?p=2351"
        )

    def test_fallback_when_not_in_ledger(self):
        self.assertEqual(
            resolve_guid(426, {}), "http://www.tsujileaks.com/?p=426"
        )


if __name__ == "__main__":
    unittest.main()
