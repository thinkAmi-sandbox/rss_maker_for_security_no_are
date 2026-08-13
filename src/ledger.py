"""guid 台帳: 公式フィードで観測した guid の蓄積記録。

台帳はリポジトリにコミットされる CSV(p,guid,first_seen、p 昇順)。
guid は WordPress の仕様上、投稿作成時に固定され以後不変のため、
初観測1回で確定とみなす。更新は追記のみで、既存行は書き換えない。
"""

import csv
import io
from dataclasses import dataclass

HEADER = ("p", "guid", "first_seen")


class LedgerError(Exception):
    """台帳の形式不正、または guid 不変の前提の崩れ(fail-loud)。"""


@dataclass(frozen=True)
class LedgerEntry:
    article_number: int
    guid: str
    first_seen: str  # ISO 8601 日付


@dataclass(frozen=True)
class LedgerUpdate:
    entries: dict  # dict[int, LedgerEntry] 更新後の全記録
    additions: list  # list[LedgerEntry] 今回追記された分


def parse_ledger(text: str) -> dict:
    """台帳 CSV を dict[p 番号, LedgerEntry] に読み込む。空文字列は空台帳。"""
    if text.strip() == "":
        return {}
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if tuple(rows[0]) != HEADER:
        raise LedgerError(f"台帳のヘッダが不正です: {rows[0]!r}")
    entries = {}
    for row in rows[1:]:
        if len(row) != len(HEADER):
            raise LedgerError(f"台帳の行が不正です: {row!r}")
        try:
            p = int(row[0])
        except ValueError:
            raise LedgerError(f"台帳の p 列が数値ではありません: {row!r}") from None
        if p in entries:
            raise LedgerError(f"台帳に重複した p 番号があります: p={p}")
        entries[p] = LedgerEntry(article_number=p, guid=row[1], first_seen=row[2])
    return entries


def plan_update(entries: dict, feed_entries, today: str) -> LedgerUpdate:
    """フィードの観測結果を台帳に反映する計画を立てる(純粋)。

    - 台帳にない p 番号 → 追記(first_seen = today)
    - 既知の p 番号で guid 文字列が食い違う → guid 不変の前提の崩れとしてエラー。
      公式が過去回を別 guid で再配信し始めた場合、本ツールは役目を終える
    """
    updated = dict(entries)
    additions = []
    for fe in feed_entries:
        known = updated.get(fe.article_number)
        if known is None:
            entry = LedgerEntry(
                article_number=fe.article_number, guid=fe.guid, first_seen=today
            )
            updated[fe.article_number] = entry
            additions.append(entry)
        elif known.guid != fe.guid:
            raise LedgerError(
                f"guid が台帳の記録と食い違っています: p={fe.article_number} "
                f"台帳={known.guid!r} フィード={fe.guid!r}"
            )
    return LedgerUpdate(entries=updated, additions=additions)


def render_ledger(entries: dict) -> str:
    """台帳を p 昇順の CSV 文字列にする(git 差分が追記行だけになるように)。"""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    for p in sorted(entries):
        e = entries[p]
        writer.writerow([e.article_number, e.guid, e.first_seen])
    return out.getvalue()
