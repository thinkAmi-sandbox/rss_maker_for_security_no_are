import unittest
from pathlib import Path

from src.diff import FeedError, compute_diff, missing_from_csv, parse_feed

FIXTURES = Path(__file__).parent / "fixtures"

FEED_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
{items}
</channel></rss>"""


def feed_with_guids(*guids):
    items = "\n".join(
        f'<item><guid isPermaLink="false">{g}</guid></item>' for g in guids
    )
    return FEED_TEMPLATE.format(items=items)


class ParseFeedTest(unittest.TestCase):
    def test_real_fixture(self):
        """実フィード断片: http guid(p=491, 1587)と https guid(p=2351)の混在。"""
        text = (FIXTURES / "feed_fragment.xml").read_text(encoding="utf-8")
        entries = parse_feed(text)
        by_p = {e.article_number: e.guid for e in entries}
        self.assertEqual(
            by_p,
            {
                2351: "https://www.tsujileaks.com/?p=2351",
                1587: "http://www.tsujileaks.com/?p=1587",
                491: "http://www.tsujileaks.com/?p=491",
            },
        )

    def test_both_schemes_accepted(self):
        text = feed_with_guids(
            "http://www.tsujileaks.com/?p=1",
            "https://www.tsujileaks.com/?p=2",
        )
        entries = parse_feed(text)
        self.assertEqual([e.article_number for e in entries], [1, 2])

    def test_empty_feed_fails(self):
        with self.assertRaises(FeedError) as ctx:
            parse_feed(FEED_TEMPLATE.format(items=""))
        self.assertIn("item がありません", str(ctx.exception))

    def test_broken_xml_fails(self):
        with self.assertRaises(FeedError):
            parse_feed("<html>error page</html><oops")

    def test_format_drift_fails(self):
        drifted = [
            "https://tsujileaks.com/?p=100",  # www なし
            "https://www.tsujileaks.com/episode/100",  # pretty permalink
            "https://www.tsujileaks.com/?p=100&x=1",  # 余分なクエリ
            "",  # guid なし
        ]
        for guid in drifted:
            with self.assertRaises(FeedError, msg=guid):
                parse_feed(feed_with_guids("http://www.tsujileaks.com/?p=1", guid))

    def test_same_p_conflicting_guid_fails(self):
        with self.assertRaises(FeedError):
            parse_feed(
                feed_with_guids(
                    "http://www.tsujileaks.com/?p=5",
                    "https://www.tsujileaks.com/?p=5",
                )
            )


class ComputeDiffTest(unittest.TestCase):
    def test_pushed_out_only(self):
        """フィードにない p 番号だけが出力対象になる。"""
        targets = [10, 400, 426, 491, 2351]
        feed = [491, 1587, 2351]
        self.assertEqual(compute_diff(targets, feed), [10, 400, 426])

    def test_scheme_independent(self):
        """guid のスキームに関係なく p 番号一致で在中と判定される。

        (文字列比較なら https 配信の回を「フィード外」と誤判定する)
        """
        entries = parse_feed(
            feed_with_guids("https://www.tsujileaks.com/?p=100")
        )
        feed_numbers = [e.article_number for e in entries]
        self.assertEqual(compute_diff([100, 200], feed_numbers), [200])

    def test_empty_diff(self):
        self.assertEqual(compute_diff([1, 2], [1, 2, 3]), [])

    def test_all_pushed_out(self):
        """フィード保持件数の縮小: 差分が増えるだけでエラーにしない。"""
        self.assertEqual(compute_diff([1, 2, 3], [3]), [1, 2])


class MissingFromCsvTest(unittest.TestCase):
    def test_detects_stalled_fan_repo(self):
        self.assertEqual(missing_from_csv([1, 2, 3], [1]), [2, 3])

    def test_none_missing(self):
        self.assertEqual(missing_from_csv([1, 2], [1, 2, 3]), [])


if __name__ == "__main__":
    unittest.main()
