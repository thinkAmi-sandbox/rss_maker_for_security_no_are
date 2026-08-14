import csv
import io
import unittest
from pathlib import Path

from src.load import (
    LoadError,
    extract_article_number,
    load_csv,
    parse_rows,
    select_targets,
)

FIXTURES = Path(__file__).parent / "fixtures"

HEADER = "season,num,id,title,published_datetime,recorded_date,url,audio_url,image_url"


def rows_from(text: str):
    return parse_rows(csv.DictReader(io.StringIO(text)))


class ExtractArticleNumberTest(unittest.TestCase):
    def test_valid_urls(self):
        cases = {
            "https://www.tsujileaks.com/?p=10": 10,
            "https://www.tsujileaks.com/?p=426": 426,
            "https://www.tsujileaks.com/?p=2351": 2351,
        }
        for url, expected in cases.items():
            self.assertEqual(extract_article_number(url), expected)

    def test_invalid_urls(self):
        cases = [
            "https://atmarkit.itmedia.co.jp/ait/articles/1511/10/news022.html",
            "http://www.tsujileaks.com/?p=10",  # CSV の url は https のみ
            "https://tsujileaks.com/?p=10",  # www なしは対象外
            "https://www.tsujileaks.com/?p=10&foo=1",  # 余分なクエリ
            "https://www.tsujileaks.com/episode/10",
            "",
        ]
        for url in cases:
            self.assertIsNone(extract_article_number(url), url)


class ParseRowsTest(unittest.TestCase):
    def test_fixture_loads(self):
        episodes = load_csv(str(FIXTURES / "fan_rows.csv"))
        self.assertEqual(len(episodes), 8)
        first = episodes[0]
        self.assertEqual(first.season, "1")
        self.assertEqual(first.article_number, 10)

    def test_missing_required_column(self):
        text = "season,num,title\n1,1,foo\n"
        with self.assertRaises(LoadError) as ctx:
            rows_from(text)
        self.assertIn("published_datetime", str(ctx.exception))

    def test_empty_csv(self):
        with self.assertRaises(LoadError):
            rows_from(HEADER + "\n")

    def test_header_only_with_missing_column_names_the_column(self):
        """データ行ゼロでも、列欠落は欠けている列名を明示してエラーになる。"""
        with self.assertRaises(LoadError) as ctx:
            rows_from("season,num,title\n")
        self.assertIn("published_datetime", str(ctx.exception))


class SelectTargetsTest(unittest.TestCase):
    def test_fixture_selection(self):
        """実データ断片: S1×2 + S3×3 が対象、S2×3 が除外。"""
        episodes = load_csv(str(FIXTURES / "fan_rows.csv"))
        selection = select_targets(episodes)
        self.assertEqual(len(selection.targets), 5)
        self.assertEqual(len(selection.excluded), 3)
        self.assertTrue(all(r.season == "2" for r in selection.excluded))
        self.assertEqual(
            sorted(r.article_number for r in selection.targets),
            [10, 400, 426, 491, 2351],
        )

    def test_non_s2_row_with_empty_audio_fails(self):
        text = (
            HEADER + "\n"
            '3,99,S3#99,テスト回,2020-01-01T20:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=999,,\n"
        )
        with self.assertRaises(LoadError) as ctx:
            select_targets(rows_from(text))
        self.assertIn("S2 以外", str(ctx.exception))

    def test_non_s2_row_with_bad_url_fails(self):
        text = (
            HEADER + "\n"
            '1,99,S1#99,テスト回,2020-01-01T20:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/episode/999,https://www.tsujileaks.com/media/x.m4a,\n"
        )
        with self.assertRaises(LoadError):
            select_targets(rows_from(text))

    def test_s2_row_meeting_target_condition_fails(self):
        """逆方向の不変条件: S2 が採用条件を満たしたら動画連載回の混入としてエラー。"""
        text = (
            HEADER + "\n"
            '2,29,S2#29,C2（C&C）とは【動画】,2016-07-27T05:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=777,https://www.tsujileaks.com/media/s2.mp3,\n"
        )
        with self.assertRaises(LoadError) as ctx:
            select_targets(rows_from(text))
        self.assertIn("採用条件", str(ctx.exception))

    def test_unknown_season_fails(self):
        text = (
            HEADER + "\n"
            '4,1,S4#1,新シーズン,2030-01-01T20:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=9999,https://www.tsujileaks.com/media/y.m4a,\n"
        )
        with self.assertRaises(LoadError) as ctx:
            select_targets(rows_from(text))
        self.assertIn("未知の season", str(ctx.exception))

    def test_target_row_with_bad_published_datetime_fails(self):
        """処理対象行の published_datetime 異常は行を特定した LoadError になる。"""
        text = (
            HEADER + "\n"
            '3,300,S3#300,テスト回,2026/01/05 20:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=2000,https://www.tsujileaks.com/media/x.mp3,\n"
        )
        with self.assertRaises(LoadError) as ctx:
            select_targets(rows_from(text))
        message = str(ctx.exception)
        self.assertIn("published_datetime", message)
        self.assertIn("num=300", message)
        self.assertIn("2026/01/05 20:00", message)

    def test_excluded_row_with_bad_published_datetime_is_tolerated(self):
        """除外行(S2)は日時を使わないため、異常値でも生成を止めない。"""
        text = (
            HEADER + "\n"
            '2,1,S2#1,動画回,不正な日時,1900-01-01,'
            "https://atmarkit.itmedia.co.jp/ait/articles/1511/10/news022.html,,\n"
        )
        selection = select_targets(rows_from(text))
        self.assertEqual(len(selection.excluded), 1)

    def test_duplicate_article_number_fails(self):
        text = (
            HEADER + "\n"
            '3,1,S3#1,回A,2020-01-01T20:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=100,https://www.tsujileaks.com/media/a.mp3,\n"
            '3,2,S3#2,回B,2020-01-08T20:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=100,https://www.tsujileaks.com/media/b.mp3,\n"
        )
        with self.assertRaises(LoadError) as ctx:
            select_targets(rows_from(text))
        self.assertIn("重複", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
