import io
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.cli import (
    FAN_REPO_URL,
    OFFICIAL_SITE,
    OFFICIAL_TITLE,
    REPO_URL,
    build_channel_meta,
    fan_repo_commit,
    run,
    summarize,
)
from src.fetch import FEED_URL, HeadResult

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHeadAllAlive:
    def __call__(self, url):
        return HeadResult(ok=True, content_type="audio/mp4", content_length=123)


class ChannelMetaTest(unittest.TestCase):
    """仕様(RSS 2.0 の生成)の channel メタ MUST 3点を実装関数で検証する。"""

    def test_contains_required_elements(self):
        meta = build_channel_meta(
            generated_at="2026-08-13T16:00:00+09:00", commit="abc1234"
        )
        self.assertIn("非公式", meta.title)
        self.assertEqual(meta.link, OFFICIAL_SITE)
        self.assertIn("2026-08-13T16:00:00+09:00", meta.description)  # 生成日時
        self.assertIn("abc1234", meta.description)  # ファンリポジトリの commit
        self.assertIn(FAN_REPO_URL, meta.description)  # データ出典
        self.assertIn(REPO_URL, meta.description)  # 本リポジトリ


class FanRepoCommitTest(unittest.TestCase):
    def test_untracked_csv_returns_unknown(self):
        """zip 展開相当(git 追跡外の CSV)では、親方向 walk で見つかる
        無関係なリポジトリのハッシュを出典として記録しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            (Path(tmp) / "tracked.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", tmp, "add", "tracked.txt"], check=True)
            subprocess.run(
                [
                    "git", "-C", tmp,
                    "-c", "user.email=test@example.com",
                    "-c", "user.name=test",
                    "commit", "-q", "-m", "init",
                ],
                check=True,
            )
            untracked = Path(tmp) / "references" / "data.csv"
            untracked.parent.mkdir()
            untracked.write_text("x", encoding="utf-8")
            self.assertEqual(fan_repo_commit(str(untracked)), "unknown")

    def test_returns_head_of_repo_containing_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            csv_path = Path(tmp) / "data.csv"
            csv_path.write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", tmp, "add", "data.csv"], check=True)
            subprocess.run(
                [
                    "git", "-C", tmp,
                    "-c", "user.email=test@example.com",
                    "-c", "user.name=test",
                    "commit", "-q", "-m", "init",
                ],
                check=True,
            )
            expected = subprocess.run(
                ["git", "-C", tmp, "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(fan_repo_commit(str(csv_path)), expected)


class SummarizeTest(unittest.TestCase):
    def test_contains_counts_and_warnings(self):
        counts = {
            "feed": 300,
            "csv_rows": 387,
            "targets": 342,
            "excluded": 45,
            "output": 42,
            "output_by_season": {"1": 26, "3": 16},
            "dead": 0,
            "ledger_added": 300,
        }
        text = summarize(counts, ["テスト警告"])
        self.assertIn("300", text)
        self.assertIn("S1=26, S3=16", text)
        self.assertIn("警告: テスト警告", text)


class PipelineTest(unittest.TestCase):
    """フィクスチャ(実データ断片)でパイプライン全体を通す。

    フィード断片は p=491, 1587, 2351 を含むため、CSV 断片の処理対象
    (p=10, 400, 426, 491, 2351)のうち出力対象は p=10, 400, 426 になる。
    """

    def run_pipeline(self, tmp):
        out = io.StringIO()
        feed_text = (FIXTURES / "feed_fragment.xml").read_text(encoding="utf-8")
        code = run(
            [
                "--csv", str(FIXTURES / "fan_rows.csv"),
                "--output", str(Path(tmp) / "archive.xml"),
                "--ledger", str(Path(tmp) / "ledger.csv"),
            ],
            feed_fetcher=lambda url: feed_text,
            head_func=FakeHeadAllAlive(),
            sleep_func=lambda s: None,
            out=out,
        )
        return code, out.getvalue(), tmp

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, summary, _ = self.run_pipeline(tmp)
            self.assertEqual(code, 0)

            root = ET.parse(Path(tmp) / "archive.xml").getroot()
            guids = [g.text for g in root.findall("./channel/item/guid")]
            # 出力はフィードにない p=10, 400, 426 のみ(全て合成 http guid)
            self.assertEqual(
                guids,
                [
                    "http://www.tsujileaks.com/?p=10",
                    "http://www.tsujileaks.com/?p=400",
                    "http://www.tsujileaks.com/?p=426",
                ],
            )
            enclosures = root.findall("./channel/item/enclosure")
            for enc in enclosures:
                self.assertTrue(enc.get("url").startswith("https://"))

            # 台帳にはフィードの3件が観測値そのままで記録される
            ledger_text = (Path(tmp) / "ledger.csv").read_text(encoding="utf-8")
            self.assertIn("491,http://www.tsujileaks.com/?p=491,", ledger_text)
            self.assertIn("2351,https://www.tsujileaks.com/?p=2351,", ledger_text)

            # サマリ: フィード3件・出力3件(S1=2, S3=1)・除外3件・警告1件
            self.assertIn("フィード item 件数        : 3", summary)
            self.assertIn("S1=2, S3=1", summary)
            self.assertIn("除外(S2・動画連載時代) : 3", summary)
            # p=1587 は CSV 断片に無いため更新停止の警告が出る
            self.assertIn("1587", summary)

    def test_rerun_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_pipeline(tmp)
            first_ledger = (Path(tmp) / "ledger.csv").read_text(encoding="utf-8")
            first_items = self.item_signature(Path(tmp) / "archive.xml")

            code, summary, _ = self.run_pipeline(tmp)
            self.assertEqual(code, 0)
            self.assertEqual(
                (Path(tmp) / "ledger.csv").read_text(encoding="utf-8"), first_ledger
            )
            self.assertEqual(
                self.item_signature(Path(tmp) / "archive.xml"), first_items
            )
            self.assertIn("guid 台帳への追記         : 0", summary)

    def test_source_url_follows_feed_url_option(self):
        """--feed-url を差し替えると全 item の <source url> が追随する。

        「宣言 = 差分計算に実際に使った URL」の契約の直接テスト。
        render 側でフィード URL の定数を二重に持つとここで落ちる。
        """
        other_feed = "https://example.test/?feed=podcast"
        feed_text = (FIXTURES / "feed_fragment.xml").read_text(encoding="utf-8")
        used_urls = []

        def recording_fetcher(url):
            used_urls.append(url)
            return feed_text

        with tempfile.TemporaryDirectory() as tmp:
            run(
                [
                    "--csv", str(FIXTURES / "fan_rows.csv"),
                    "--output", str(Path(tmp) / "archive.xml"),
                    "--ledger", str(Path(tmp) / "ledger.csv"),
                    "--feed-url", other_feed,
                ],
                feed_fetcher=recording_fetcher,
                head_func=FakeHeadAllAlive(),
                sleep_func=lambda s: None,
                out=io.StringIO(),
            )
            # 取得に使った URL と、宣言された URL が一致する
            self.assertEqual(used_urls, [other_feed])
            root = ET.parse(Path(tmp) / "archive.xml").getroot()
            sources = root.findall("./channel/item/source")
            self.assertTrue(sources)
            self.assertEqual({s.get("url") for s in sources}, {other_feed})
            self.assertEqual({s.text for s in sources}, {OFFICIAL_TITLE})

    def test_default_run_declares_official_feed_url(self):
        feed_text = (FIXTURES / "feed_fragment.xml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            run(
                [
                    "--csv", str(FIXTURES / "fan_rows.csv"),
                    "--output", str(Path(tmp) / "archive.xml"),
                    "--ledger", str(Path(tmp) / "ledger.csv"),
                ],
                feed_fetcher=lambda url: feed_text,
                head_func=FakeHeadAllAlive(),
                sleep_func=lambda s: None,
                out=io.StringIO(),
            )
            root = ET.parse(Path(tmp) / "archive.xml").getroot()
            sources = root.findall("./channel/item/source")
            self.assertEqual({s.get("url") for s in sources}, {FEED_URL})

    def test_remote_mode_records_download_sha(self):
        """--csv 省略時はリモート取得され、sha が channel 説明文に記録される。"""
        sha = "cafe0123456789"
        csv_text = (FIXTURES / "fan_rows.csv").read_text(encoding="utf-8")
        feed_text = (FIXTURES / "feed_fragment.xml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            code = run(
                [
                    "--output", str(Path(tmp) / "archive.xml"),
                    "--ledger", str(Path(tmp) / "ledger.csv"),
                ],
                feed_fetcher=lambda url: feed_text,
                csv_fetcher=lambda: (csv_text, sha),
                head_func=FakeHeadAllAlive(),
                sleep_func=lambda s: None,
                out=io.StringIO(),
            )
            self.assertEqual(code, 0)
            root = ET.parse(Path(tmp) / "archive.xml").getroot()
            description = root.findtext("./channel/description")
            self.assertIn(f"commit {sha}", description)

    def test_excluded_row_with_p_number_does_not_trigger_stall_warning(self):
        """p 番号を持つが除外された行(S2)は「CSV 未収載」の誤警告にしない。"""
        csv_text = (
            "season,num,id,title,published_datetime,recorded_date,url,audio_url,image_url\n"
            '2,1,S2#1,動画回,2015-11-10T05:00+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=500,,\n"
            '1,1,S1#1,第1回,2011-02-21T01:46+09:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=10,http://www.tsujileaks.com/media/a.m4a,\n"
        )
        feed_text = (
            '<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
            '<item><guid isPermaLink="false">http://www.tsujileaks.com/?p=500</guid></item>'
            "</channel></rss>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "in.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out = io.StringIO()
            run(
                [
                    "--csv", str(csv_path),
                    "--output", str(Path(tmp) / "a.xml"),
                    "--ledger", str(Path(tmp) / "l.csv"),
                ],
                feed_fetcher=lambda url: feed_text,
                head_func=FakeHeadAllAlive(),
                sleep_func=lambda s: None,
                out=out,
            )
            summary = out.getvalue()
            self.assertNotIn("警告", summary)  # p=500 は CSV に存在するので警告しない

    def test_failure_before_render_leaves_no_files(self):
        """入力異常で失敗したとき、台帳も archive.xml も書かれない。"""
        bad_csv = (
            "season,num,id,title,published_datetime,recorded_date,url,audio_url,image_url\n"
            '3,300,S3#300,テスト回,2026/01/05 20:00,1900-01-01,'
            "https://www.tsujileaks.com/?p=2000,https://www.tsujileaks.com/media/x.mp3,\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "in.csv"
            csv_path.write_text(bad_csv, encoding="utf-8")
            with self.assertRaises(Exception):
                run(
                    [
                        "--csv", str(csv_path),
                        "--output", str(Path(tmp) / "archive.xml"),
                        "--ledger", str(Path(tmp) / "ledger.csv"),
                    ],
                    feed_fetcher=lambda url: "",
                    head_func=FakeHeadAllAlive(),
                    sleep_func=lambda s: None,
                    out=io.StringIO(),
                )
            self.assertFalse((Path(tmp) / "archive.xml").exists())
            self.assertFalse((Path(tmp) / "ledger.csv").exists())

    @staticmethod
    def item_signature(path):
        root = ET.parse(path).getroot()
        return [
            (
                item.findtext("title"),
                item.findtext("guid"),
                item.find("enclosure").get("url"),
            )
            for item in root.findall("./channel/item")
        ]


if __name__ == "__main__":
    unittest.main()
