"""結線: 引数解釈・パイプライン実行・実行サマリ表示。

パイプライン:
  CSV 読み込み → フィード取得(guid 形式アサーション)→ 台帳更新 →
  p 番号差分 → 音源生存確認 → archive.xml 書き出し → サマリ表示

件数(フィード件数・差分件数)は機械判定に使わない。フィードの保持
件数は配信側の設定値で可変のため、判断は実行サマリの目視に委ねる。
機械判定はフィード0件での中断(diff.parse_feed)のみ。
"""

import argparse
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from src import diff, fetch, guid, ledger, load, render

JST = timezone(timedelta(hours=9))
OFFICIAL_SITE = "https://www.tsujileaks.com/"
# 出典宣言(<source>)のテキスト。公式フィードの channel title と同一の、
# 出典フィード側の番組名。アーカイブ自身の channel title とは別物
OFFICIAL_TITLE = "セキュリティのアレ"
REPO_URL = "https://github.com/thinkAmi/rss_maker_for_security_no_are"
FAN_REPO_URL = "https://github.com/BerandaMegane/Security-no-ARE-words"


def fan_repo_commit(csv_path: str) -> str:
    """ローカル CSV(--csv 指定時)のコミットハッシュを引く。

    git は指定ディレクトリが管理外だと親方向に walk するため、無関係な
    リポジトリ(例: 本リポジトリ自身)の HEAD を拾い得る。誤ったハッシュを
    出典として記録しないよう、その CSV が見つかったリポジトリの追跡
    ファイルであることを確認できた場合だけハッシュを返す。
    取れなければ unknown(生成は続行する。再現性の記録が目的のため)。
    """
    parent = str(Path(csv_path).parent)
    try:
        tracked = subprocess.run(
            ["git", "-C", parent, "ls-files", "--error-unmatch", Path(csv_path).name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if tracked.returncode != 0:
            return "unknown"
        result = subprocess.run(
            ["git", "-C", parent, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def build_channel_meta(generated_at: str, commit: str) -> render.ChannelMeta:
    return render.ChannelMeta(
        title="セキュリティのアレ 過去回アーカイブ(非公式)",
        link=OFFICIAL_SITE,
        description=(
            "ポッドキャスト「セキュリティのアレ」の公式フィードから押し出された"
            "過去回を再構成した非公式アーカイブです。音源はすべて公式サーバーを"
            "指しています(再ホストしていません)。 "
            f"生成日時: {generated_at} / "
            f"データ出典: {FAN_REPO_URL} (commit {commit}) / "
            f"生成ツール: {REPO_URL}"
        ),
    )


def summarize(counts: dict, warnings: list) -> str:
    # 内訳は season ごとの集計から組み立てる(合計が出力件数と必ず一致する)
    breakdown = ", ".join(
        f"S{season}={n}" for season, n in sorted(counts["output_by_season"].items())
    )
    lines = [
        "==== 実行サマリ ====",
        f"フィード item 件数        : {counts['feed']}",
        f"CSV 行数                  : {counts['csv_rows']}",
        f"処理対象                  : {counts['targets']}",
        f"除外(S2・動画連載時代) : {counts['excluded']}",
        f"出力対象                  : {counts['output']}({breakdown})",
        f"リンク切れ                : {counts['dead']}",
        f"guid 台帳への追記         : {counts['ledger_added']}",
    ]
    for w in warnings:
        lines.append(f"警告: {w}")
    lines.append("====================")
    return "\n".join(lines)


def run(
    argv=None,
    *,
    feed_fetcher=None,
    csv_fetcher=None,
    head_func=None,
    sleep_func=None,
    out=None,
):
    parser = argparse.ArgumentParser(
        description="セキュリティのアレ 過去回アーカイブフィード生成"
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="ローカルの自動更新 CSV のパス(省略時はファンリポジトリの main から直接取得)",
    )
    parser.add_argument("--output", default="archive.xml", help="出力する RSS のパス")
    parser.add_argument("--ledger", default="data/guid_ledger.csv", help="guid 台帳のパス")
    parser.add_argument("--feed-url", default=fetch.FEED_URL, help="現行フィードの URL")
    args = parser.parse_args(argv)

    feed_fetcher = feed_fetcher or fetch.fetch_feed
    csv_fetcher = csv_fetcher or fetch.fetch_fan_csv
    head_func = head_func or fetch.head
    sleep_func = sleep_func or time.sleep
    out = out or sys.stdout

    # 1. CSV の取得と選別(S2 除外の不変条件を含む)
    #    既定はリモート取得(sha 固定・メモリ上で処理)。--csv はローカル指定
    if args.csv:
        episodes = load.load_csv(args.csv)
        source_commit = fan_repo_commit(args.csv)
    else:
        csv_text, source_commit = csv_fetcher()
        episodes = load.load_csv_text(csv_text)
    selection = load.select_targets(episodes)

    # 2. フィード取得(item 0件・guid 形式ドリフトは diff 内で fail-loud)
    feed_entries = diff.parse_feed(feed_fetcher(args.feed_url))

    # 3. 台帳更新(既知 p の guid 食い違いは fail-loud)
    ledger_path = Path(args.ledger)
    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    update = ledger.plan_update(
        ledger.parse_ledger(ledger_text),
        feed_entries,
        today=date.today().isoformat(),
    )

    # 4. 差分(p 番号ベース)
    target_by_p = {row.article_number: row for row in selection.targets}
    feed_numbers = [e.article_number for e in feed_entries]
    output_numbers = diff.compute_diff(target_by_p.keys(), feed_numbers)
    # 更新停止の警告は「CSV 全体」と比較する(除外ポリシーとは独立の質問のため)
    csv_numbers = {r.article_number for r in episodes if r.article_number is not None}
    stalled = diff.missing_from_csv(feed_numbers, csv_numbers)

    # 5. 音源生存確認(順次・間隔付き)
    items = []
    dead_count = 0
    for i, p in enumerate(output_numbers):
        row = target_by_p[p]
        https_url = render.to_https(row.audio_url)
        if i > 0:
            sleep_func(fetch.REQUEST_INTERVAL_SECONDS)
        check = fetch.check_audio(
            https_url, row.audio_url, head_func=head_func, sleep_func=sleep_func
        )
        if not check.https_alive:
            dead_count += 1
        items.append(
            render.ArchiveItem(
                title=row.title,
                guid=guid.resolve_guid(p, update.entries),
                article_url=row.url,
                enclosure_url=https_url,
                original_audio_url=row.audio_url,
                published_datetime=row.published_datetime,
                audio=render.AudioStatus(
                    https_alive=check.https_alive,
                    http_alive=check.http_alive,
                    content_type=check.content_type,
                    content_length=check.content_length,
                    checked_at=datetime.now(JST).isoformat(timespec="seconds"),
                ),
            )
        )

    # 6. 書き出し。レンダリングを先に完成させ、成功したときだけ永続化する
    # (途中で失敗したとき「台帳だけ更新済み」の中途半端な状態を残さない)
    channel = build_channel_meta(
        generated_at=datetime.now(JST).isoformat(timespec="seconds"),
        commit=source_commit,
    )
    # 出典宣言の url は、実際にフィード取得・差分計算に使った URL をそのまま渡す
    feed_xml = render.build_feed(
        channel, items, source_url=args.feed_url, source_title=OFFICIAL_TITLE
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(ledger.render_ledger(update.entries), encoding="utf-8")
    Path(args.output).write_text(feed_xml, encoding="utf-8")

    # 7. サマリ
    warnings = []
    if stalled:
        warnings.append(
            "フィードに在るのに CSV に無い p 番号があります"
            f"(ファンリポジトリの更新停止の疑い): {len(stalled)}件 {stalled}"
        )
    output_by_season = Counter(target_by_p[p].season for p in output_numbers)
    counts = {
        "feed": len(feed_entries),
        "csv_rows": len(episodes),
        "targets": len(selection.targets),
        "excluded": len(selection.excluded),
        "output": len(items),
        "output_by_season": dict(output_by_season),
        "dead": dead_count,
        "ledger_added": len(update.additions),
    }
    print(summarize(counts, warnings), file=out)
    return 0


def main():
    try:
        sys.exit(run())
    except (load.LoadError, diff.FeedError, ledger.LedgerError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
