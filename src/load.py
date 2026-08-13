"""ファン CSV の解釈・検証・処理対象の選別。

入力はファンリポジトリの自動更新 CSV(蓄積型・ヘッダ付き)。
列は必ずヘッダ名でアクセスする。recorded_date はダミー値と実日付が
混在する信頼できない列のため、読み取り自体を行わない。
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

REQUIRED_COLUMNS = ("season", "num", "title", "published_datetime", "url", "audio_url")

# 記事番号を持つ url の厳密な形式。CSV の url は RSS の <link> 由来で常に https
ARTICLE_URL_RE = re.compile(r"^https://www\.tsujileaks\.com/\?p=(\d+)$")

KNOWN_SEASONS = ("1", "2", "3")

# 除外が許されるのはこの season のみ(@IT 動画連載時代)。
# ポリシー決定: 本ツールは音声ポッドキャストのアーカイブであり動画連載は対象外
VIDEO_SEASON = "2"


class LoadError(Exception):
    """CSV の内容が前提を満たさない(fail-loud で生成を中断する)。"""


@dataclass(frozen=True)
class EpisodeRow:
    season: str
    num: str
    title: str
    published_datetime: str
    url: str
    audio_url: str
    article_number: Optional[int]


@dataclass(frozen=True)
class Selection:
    targets: list  # list[EpisodeRow] 処理対象(S1+S3)
    excluded: list  # list[EpisodeRow] 除外(S2 のみであることを検証済み)


def extract_article_number(url: str) -> Optional[int]:
    m = ARTICLE_URL_RE.match(url.strip())
    return int(m.group(1)) if m else None


def parse_rows(dict_rows) -> list:
    """csv.DictReader の行を EpisodeRow に変換する。必須列の欠落は即エラー。

    列の検証はヘッダ(fieldnames)に対して行う。データ行の有無と独立に
    「どの列が欠けているか」を示すため。
    """
    fieldnames = dict_rows.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise LoadError(f"CSV に必須列がありません: {', '.join(missing)}")
    rows = list(dict_rows)
    if not rows:
        raise LoadError("CSV にデータ行がありません")
    episodes = []
    for r in rows:
        episodes.append(
            EpisodeRow(
                season=(r["season"] or "").strip(),
                num=(r["num"] or "").strip(),
                title=(r["title"] or "").strip(),
                published_datetime=(r["published_datetime"] or "").strip(),
                url=(r["url"] or "").strip(),
                audio_url=(r["audio_url"] or "").strip(),
                article_number=extract_article_number(r["url"] or ""),
            )
        )
    return episodes


def load_csv(path: str) -> list:
    with open(path, encoding="utf-8", newline="") as f:
        return parse_rows(csv.DictReader(f))


def load_csv_text(text: str) -> list:
    """リモート取得した CSV(メモリ上の文字列)を読み込む。"""
    return parse_rows(csv.DictReader(io.StringIO(text)))


def select_targets(episodes) -> Selection:
    """処理対象(記事番号あり・音源 URL あり)を選別する。

    不変条件: 除外集合と S2(season == 2)は一致する。双方向で検査する:
    - S2 以外の行が除外条件に合致 → 正当な回の無言の欠落を防ぐため即エラー
    - S2 の行が採用条件に合致 → 動画連載回の無言の混入を防ぐため即エラー
    """
    targets = []
    excluded = []
    seen_numbers = {}
    for row in episodes:
        if row.season not in KNOWN_SEASONS:
            raise LoadError(
                f"未知の season です: season={row.season!r} num={row.num} title={row.title!r}"
            )
        is_target = row.article_number is not None and row.audio_url != ""
        if is_target:
            # 処理対象の published_datetime は pubDate 変換に使うため、
            # ここで解釈可能性を検証する(render 段階での爆発を防ぐ)。
            # 除外行(S2)は日時を使わないので検証しない
            try:
                datetime.fromisoformat(row.published_datetime)
            except ValueError:
                raise LoadError(
                    "published_datetime を解釈できません: "
                    f"season={row.season} num={row.num} title={row.title!r} "
                    f"値={row.published_datetime!r}"
                ) from None
            if row.season == VIDEO_SEASON:
                raise LoadError(
                    "S2(動画連載時代)の行が採用条件を満たしました。"
                    "ポリシー(動画連載は対象外)とデータの前提が食い違っています: "
                    f"num={row.num} title={row.title!r} url={row.url!r}"
                )
            if row.article_number in seen_numbers:
                other = seen_numbers[row.article_number]
                raise LoadError(
                    f"記事番号が重複しています: p={row.article_number} "
                    f"({other.title!r} と {row.title!r})"
                )
            seen_numbers[row.article_number] = row
            targets.append(row)
        else:
            if row.season != VIDEO_SEASON:
                raise LoadError(
                    "S2 以外の行が除外条件に合致しました(url 形式変更または audio_url 欠落の疑い): "
                    f"season={row.season} num={row.num} title={row.title!r} "
                    f"url={row.url!r} audio_url={row.audio_url!r}"
                )
            excluded.append(row)
    return Selection(targets=targets, excluded=excluded)
