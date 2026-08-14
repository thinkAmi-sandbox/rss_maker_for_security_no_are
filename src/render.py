"""archive.xml(RSS 2.0)のレンダリング。

XML は文字列連結ではなく ElementTree で構築する。タイトルに `&` を含む
実データが存在するため、エスケープ漏れを構造的に防ぐ。

enclosure の url は生存確認の結果に依存させず、常に audio_url の https
書き換え形とする(出力の冪等性と、サーバー復活時に XML 再生成なしで
再生可能になることを優先)。生存確認の結果はタイトル接頭辞と
description のみに反映する。
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import format_datetime
from typing import Optional

DEAD_LINK_BADGE = "【音源リンク切れ】"

# HEAD が失敗して Content-Type を得られなかったときの拡張子による推定値。
# type は enclosure の必須属性のため省略できない(実値でないことは許容する。
# 公式の実配信にも audio/mp4 と audio/x-m4a の揺れがある)
FALLBACK_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}
DEFAULT_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class AudioStatus:
    """音源生存確認の結果(fetch から渡される)。"""

    https_alive: bool
    http_alive: Optional[bool]  # https 生存時は未確認なので None
    content_type: Optional[str]
    content_length: Optional[int]
    checked_at: str  # ISO 8601


@dataclass(frozen=True)
class ArchiveItem:
    title: str
    guid: str
    article_url: str  # 記事ページ(https)。<link> と description に使う
    enclosure_url: str  # 常に https 書き換え後
    original_audio_url: str  # CSV の audio_url の生値(リンク切れ時の記録用)
    published_datetime: str  # CSV の ISO 8601
    audio: AudioStatus


@dataclass(frozen=True)
class ChannelMeta:
    title: str
    link: str
    description: str


def to_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def to_rfc1123(iso_text: str) -> str:
    """CSV の published_datetime(ISO 8601、分精度・オフセット付き)を RFC 1123 に。"""
    dt = datetime.fromisoformat(iso_text)
    return format_datetime(dt)


def fallback_content_type(url: str) -> str:
    lowered = url.lower()
    for suffix, content_type in FALLBACK_CONTENT_TYPES.items():
        if lowered.endswith(suffix):
            return content_type
    return DEFAULT_CONTENT_TYPE


def item_title(item: ArchiveItem) -> str:
    if item.audio.https_alive:
        return item.title
    return DEAD_LINK_BADGE + item.title


def item_description(item: ArchiveItem) -> str:
    lines = [f"元記事: {item.article_url}"]
    audio = item.audio
    if not audio.https_alive:
        lines.append(
            f"音源リンク切れを検出({audio.checked_at} 時点): "
            f"{item.enclosure_url} は取得できませんでした。"
        )
        # 元 URL は CSV の生値をそのまま記録する(機械的な再構成をしない)。
        # enclosure と同一(元から https の回)なら、確認済みの URL の
        # 繰り返しになるだけなので追記しない
        if item.original_audio_url != item.enclosure_url:
            if audio.http_alive:
                lines.append(
                    f"元の配信 URL では取得可能でした: {item.original_audio_url}"
                )
            elif audio.http_alive is False:
                lines.append(
                    f"元の配信 URL({item.original_audio_url})でも取得できませんでした。"
                )
            else:  # None = 未確認
                lines.append("元の配信 URL は未確認です。")
    return "\n".join(lines)


def build_item_element(
    item: ArchiveItem, source_url: str, source_title: str
) -> ET.Element:
    """item 要素を組み立てる。

    source_url / source_title は出典宣言(`<source>`)の値。全 item で共通の
    フィードレベルの単一値なので ArchiveItem には持たせず、引数で受け取る。
    source_url はフィード取得・差分計算に使われた URL が cli から引き回される
    (ここでフィード URL の定数を持つと、--feed-url 差し替え時に宣言と実際の
    取得元が乖離するため)。
    """
    el = ET.Element("item")
    ET.SubElement(el, "title").text = item_title(item)
    ET.SubElement(el, "link").text = item.article_url
    guid_el = ET.SubElement(el, "guid", {"isPermaLink": "false"})
    guid_el.text = item.guid
    ET.SubElement(el, "pubDate").text = to_rfc1123(item.published_datetime)
    enclosure_attrs = {
        "url": item.enclosure_url,
        "type": item.audio.content_type or fallback_content_type(item.enclosure_url),
    }
    if item.audio.content_length is not None:
        enclosure_attrs["length"] = str(item.audio.content_length)
    ET.SubElement(el, "enclosure", enclosure_attrs)
    ET.SubElement(el, "description").text = item_description(item)
    # 出典宣言は item 末尾に固定する(RSS 2.0 上は位置自由。golden の安定のため)
    source_el = ET.SubElement(el, "source", {"url": source_url})
    source_el.text = source_title
    return el


def build_feed(channel: ChannelMeta, items, source_url: str, source_title: str) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel_el = ET.SubElement(rss, "channel")
    ET.SubElement(channel_el, "title").text = channel.title
    ET.SubElement(channel_el, "link").text = channel.link
    ET.SubElement(channel_el, "description").text = channel.description
    for item in items:
        channel_el.append(build_item_element(item, source_url, source_title))
    ET.indent(rss)
    body = ET.tostring(rss, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
