"""現行フィードの解釈と p 番号ベースの差分計算。

差分は guid 文字列比較ではなく記事番号(p 番号)で行う。公式フィードの
guid はスキーム(http/https)が投稿ごとに混在しており、文字列比較では
在中の回を「フィード外」と誤判定して全量出力に転落し得るため。
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

# フィード guid の許容形式。スキームだけが揺れる(http 73 / https 227 を実測)
FEED_GUID_RE = re.compile(r"^https?://www\.tsujileaks\.com/\?p=(\d+)$")


class FeedError(Exception):
    """フィードが前提を満たさない(fail-loud で生成を中断する)。"""


@dataclass(frozen=True)
class FeedEntry:
    article_number: int
    guid: str  # フィードが配信した文字列の無加工の転記


def parse_feed(xml_text: str) -> list:
    """フィード XML から (p 番号, guid) を抽出する。

    - item 0件は取得劣化とみなしエラー(空集合は形式検査を素通りするため)
    - 形式外の guid が1件でもあれば形式ドリフトとみなしエラー
    - item 件数の上限・下限は検査しない(保持件数は配信側の設定値)
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise FeedError(f"フィード XML を解釈できません: {e}") from e
    items = root.findall("./channel/item")
    if not items:
        raise FeedError("フィードに item がありません(取得劣化の疑い)")
    entries = []
    seen = {}
    for item in items:
        guid_el = item.find("guid")
        guid = (guid_el.text or "").strip() if guid_el is not None else ""
        m = FEED_GUID_RE.match(guid)
        if not m:
            raise FeedError(f"想定外の guid 形式です(形式ドリフトの疑い): {guid!r}")
        p = int(m.group(1))
        if p in seen and seen[p] != guid:
            raise FeedError(
                f"同一記事番号に異なる guid が配信されています: p={p} "
                f"({seen[p]!r} と {guid!r})"
            )
        if p not in seen:
            seen[p] = guid
            entries.append(FeedEntry(article_number=p, guid=guid))
    return entries


def compute_diff(target_numbers, feed_numbers) -> list:
    """出力対象 = 処理対象のうち、現行フィードに存在しない p 番号。昇順。"""
    feed_set = set(feed_numbers)
    return sorted(p for p in target_numbers if p not in feed_set)


def missing_from_csv(feed_numbers, csv_numbers) -> list:
    """フィードに在るのに CSV に無い p 番号。昇順。

    ファンリポジトリの自動更新停止の兆候を利用者が察知するための警告用。
    """
    csv_set = set(csv_numbers)
    return sorted(p for p in set(feed_numbers) if p not in csv_set)
