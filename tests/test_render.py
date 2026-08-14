import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.render import (
    ArchiveItem,
    AudioStatus,
    ChannelMeta,
    DEAD_LINK_BADGE,
    build_feed,
    build_item_element,
    to_https,
    to_rfc1123,
)

FIXTURES = Path(__file__).parent / "fixtures"

ALIVE = AudioStatus(
    https_alive=True,
    http_alive=None,
    content_type="audio/mp4",
    content_length=16323195,
    checked_at="2026-08-13T14:00:00+09:00",
)
DEAD_HTTPS_ALIVE_HTTP = AudioStatus(
    https_alive=False,
    http_alive=True,
    content_type=None,
    content_length=None,
    checked_at="2026-08-13T14:00:00+09:00",
)
DEAD_BOTH = AudioStatus(
    https_alive=False,
    http_alive=False,
    content_type=None,
    content_length=None,
    checked_at="2026-08-13T14:00:00+09:00",
)


def make_item(audio=ALIVE, title="第1回 セキュリティのポッドキャスト(仮)"):
    return ArchiveItem(
        title=title,
        guid="http://www.tsujileaks.com/?p=10",
        article_url="https://www.tsujileaks.com/?p=10",
        enclosure_url="https://www.tsujileaks.com/media/security01.m4a",
        original_audio_url="http://www.tsujileaks.com/media/security01.m4a",
        published_datetime="2011-02-21T01:46+09:00",
        audio=audio,
    )


CHANNEL = ChannelMeta(
    title="セキュリティのアレ 過去回アーカイブ(非公式)",
    link="https://www.tsujileaks.com/",
    description="非公式アーカイブ。生成: 2026-08-13 / fan repo commit: abc1234",
)

SOURCE_URL = "https://www.tsujileaks.com/?feed=podcast"
SOURCE_TITLE = "セキュリティのアレ"


def build_item(item, source_url=SOURCE_URL, source_title=SOURCE_TITLE):
    return build_item_element(item, source_url, source_title)


def build(items, source_url=SOURCE_URL, source_title=SOURCE_TITLE):
    return build_feed(CHANNEL, items, source_url, source_title)


class HelperTest(unittest.TestCase):
    def test_to_https(self):
        self.assertEqual(
            to_https("http://www.tsujileaks.com/media/a.m4a"),
            "https://www.tsujileaks.com/media/a.m4a",
        )
        self.assertEqual(
            to_https("https://www.tsujileaks.com/media/a.m4a"),
            "https://www.tsujileaks.com/media/a.m4a",
        )

    def test_to_rfc1123(self):
        self.assertEqual(
            to_rfc1123("2011-02-21T01:46+09:00"), "Mon, 21 Feb 2011 01:46:00 +0900"
        )
        self.assertEqual(
            to_rfc1123("2026-08-10T20:00+09:00"), "Mon, 10 Aug 2026 20:00:00 +0900"
        )


class ItemElementTest(unittest.TestCase):
    def test_alive_item(self):
        el = build_item(make_item(ALIVE))
        self.assertEqual(el.findtext("title"), "第1回 セキュリティのポッドキャスト(仮)")
        guid = el.find("guid")
        self.assertEqual(guid.get("isPermaLink"), "false")
        self.assertEqual(guid.text, "http://www.tsujileaks.com/?p=10")
        self.assertEqual(el.findtext("pubDate"), "Mon, 21 Feb 2011 01:46:00 +0900")
        enclosure = el.find("enclosure")
        self.assertEqual(
            enclosure.get("url"), "https://www.tsujileaks.com/media/security01.m4a"
        )
        self.assertEqual(enclosure.get("type"), "audio/mp4")
        self.assertEqual(enclosure.get("length"), "16323195")
        self.assertNotIn("リンク切れ", el.findtext("description"))

    def test_dead_https_alive_http(self):
        el = build_item(make_item(DEAD_HTTPS_ALIVE_HTTP))
        self.assertTrue(el.findtext("title").startswith(DEAD_LINK_BADGE))
        # enclosure は生存結果に関わらず https のまま
        enclosure = el.find("enclosure")
        self.assertEqual(
            enclosure.get("url"), "https://www.tsujileaks.com/media/security01.m4a"
        )
        self.assertEqual(enclosure.get("type"), "audio/mp4")  # 拡張子から補完
        self.assertIsNone(enclosure.get("length"))  # 実値が無ければ省略
        description = el.findtext("description")
        self.assertIn("2026-08-13T14:00:00+09:00", description)
        # 元 URL は CSV の生値(http)がそのまま記録される
        self.assertIn(
            "元の配信 URL では取得可能でした: http://www.tsujileaks.com/media/security01.m4a",
            description,
        )

    def test_dead_both(self):
        el = build_item(make_item(DEAD_BOTH))
        self.assertTrue(el.findtext("title").startswith(DEAD_LINK_BADGE))
        description = el.findtext("description")
        # 両スキーム死亡でも元 URL が記録される(仕様シナリオの要求)
        self.assertIn(
            "元の配信 URL(http://www.tsujileaks.com/media/security01.m4a)"
            "でも取得できませんでした",
            description,
        )

    def test_dead_https_original_unverified(self):
        """元 URL が未確認(http_alive=None)のときは断定しない。"""
        unverified = AudioStatus(
            https_alive=False,
            http_alive=None,
            content_type=None,
            content_length=None,
            checked_at="2026-08-13T14:00:00+09:00",
        )
        el = build_item(make_item(unverified))
        description = el.findtext("description")
        self.assertIn("元の配信 URL は未確認です", description)
        self.assertNotIn("取得できませんでした。\n元の配信 URL(", description)

    def test_dead_https_origin_same_url_no_redundant_line(self):
        """元から https の回(元 URL = enclosure)は元 URL の追記行を出さない。"""
        unverified = AudioStatus(
            https_alive=False,
            http_alive=None,
            content_type=None,
            content_length=None,
            checked_at="2026-08-13T14:00:00+09:00",
        )
        item = ArchiveItem(
            title="第300回 テスト",
            guid="https://www.tsujileaks.com/?p=2000",
            article_url="https://www.tsujileaks.com/?p=2000",
            enclosure_url="https://www.tsujileaks.com/media/x.mp3",
            original_audio_url="https://www.tsujileaks.com/media/x.mp3",
            published_datetime="2024-01-01T20:00+09:00",
            audio=unverified,
        )
        description = build_item(item).findtext("description")
        self.assertIn("音源リンク切れを検出", description)
        self.assertNotIn("元の配信 URL", description)  # 同一 URL の繰り返しは書かない

    def test_ampersand_title_roundtrip(self):
        """タイトルに & や < を含んでも well-formed で、パースで元に戻る。"""
        tricky = "Q&A回 <特別編> & その他"
        xml_text = build([make_item(ALIVE, title=tricky)])
        parsed = ET.fromstring(xml_text)
        self.assertEqual(parsed.findtext("./channel/item/title"), tricky)


class SourceDeclarationTest(unittest.TestCase):
    """出典宣言(podcast_player の注入検証が参照する)。"""

    def test_item_has_source_with_url_and_official_title(self):
        el = build_item(make_item(ALIVE))
        source = el.find("source")
        self.assertIsNotNone(source)
        self.assertEqual(source.get("url"), SOURCE_URL)
        # テキストは出典フィード側の番組名。アーカイブ自身の channel title ではない
        self.assertEqual(source.text, SOURCE_TITLE)
        self.assertNotEqual(source.text, CHANNEL.title)

    def test_source_is_last_element_of_item(self):
        el = build_item(make_item(ALIVE))
        self.assertEqual([child.tag for child in el][-1], "source")

    def test_all_items_share_the_same_source_url(self):
        items = [make_item(ALIVE), make_item(DEAD_BOTH, title="第2回")]
        root = ET.fromstring(build(items))
        sources = root.findall("./channel/item/source")
        self.assertEqual(len(sources), len(items))
        self.assertEqual({s.get("url") for s in sources}, {SOURCE_URL})

    def test_source_url_follows_given_value(self):
        """render はフィード URL の定数を持たず、渡された値をそのまま使う。"""
        other = "https://example.test/?feed=podcast"
        root = ET.fromstring(build([make_item(ALIVE)], source_url=other))
        self.assertEqual(root.findtext("./channel/item/source"), SOURCE_TITLE)
        self.assertEqual(root.find("./channel/item/source").get("url"), other)


class GoldenFileTest(unittest.TestCase):
    def test_golden(self):
        items = [
            make_item(ALIVE),
            ArchiveItem(
                title="第3回 のアレ & こレ",
                guid="http://www.tsujileaks.com/?p=30",
                article_url="https://www.tsujileaks.com/?p=30",
                enclosure_url="https://www.tsujileaks.com/media/tsujileaks03.m4a",
                original_audio_url="http://www.tsujileaks.com/media/tsujileaks03.m4a",
                published_datetime="2011-04-18T22:30+09:00",
                audio=DEAD_BOTH,
            ),
        ]
        actual = build(items)
        expected = (FIXTURES / "golden_archive.xml").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
