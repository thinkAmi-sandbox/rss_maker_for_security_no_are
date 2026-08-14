"""I/O: 現行フィードの取得と音源の生存確認 HEAD。

公式サーバーへの礼儀として、リクエストは順次実行・一定間隔・明示的な
User-Agent で行う。テストからは head_func / sleep_func を注入して
ネットワークなしで検証する(手書き Fake、モックライブラリ不使用)。
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

FEED_URL = "https://www.tsujileaks.com/?feed=podcast"
USER_AGENT = (
    "security-no-are-archive-feed-generator"
    " (+https://github.com/thinkAmi-sandbox/rss_maker_for_security_no_are)"
)
REQUEST_INTERVAL_SECONDS = 1.5
TIMEOUT_SECONDS = 30

# ファンリポジトリ(データ出典)。利用者は git 不要で、ツールが直接取得する
FAN_REPO = "BerandaMegane/Security-no-ARE-words"
FAN_CSV_REPO_PATH = "source/_static/セキュリティのアレ_放送回リスト_自動更新.csv"
FAN_COMMITS_API_URL = f"https://api.github.com/repos/{FAN_REPO}/commits/main"


@dataclass(frozen=True)
class HeadResult:
    ok: bool
    content_type: Optional[str] = None
    content_length: Optional[int] = None


def fetch_feed(url: str = FEED_URL, opener=urllib.request.urlopen) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=TIMEOUT_SECONDS) as res:
        return res.read().decode("utf-8")


def fetch_fan_csv(opener=urllib.request.urlopen):
    """ファンリポジトリの CSV を main の最新コミットに固定して取得する。

    先に GitHub API で main の sha を確定し、その sha の raw URL から
    ダウンロードする。2リクエストの間に push が挟まっても、記録する
    ハッシュと取得内容が食い違わないことが構造的に保証される。
    内容はメモリ上で処理し、ファイルには保存しない。

    Returns:
        (csv_text, sha)
    """
    req = urllib.request.Request(
        FAN_COMMITS_API_URL, headers={"User-Agent": USER_AGENT}
    )
    with opener(req, timeout=TIMEOUT_SECONDS) as res:
        sha = json.loads(res.read().decode("utf-8"))["sha"]
    raw_url = (
        f"https://raw.githubusercontent.com/{FAN_REPO}/{sha}/"
        + urllib.parse.quote(FAN_CSV_REPO_PATH)
    )
    req = urllib.request.Request(raw_url, headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=TIMEOUT_SECONDS) as res:
        return res.read().decode("utf-8"), sha


def head(url: str, opener=urllib.request.urlopen) -> HeadResult:
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": USER_AGENT}
    )
    try:
        with opener(req, timeout=TIMEOUT_SECONDS) as res:
            if res.status != 200:
                return HeadResult(ok=False)
            length_text = res.headers.get("Content-Length")
            return HeadResult(
                ok=True,
                content_type=res.headers.get("Content-Type"),
                content_length=int(length_text) if length_text else None,
            )
    except (urllib.error.URLError, OSError, ValueError):
        return HeadResult(ok=False)


@dataclass(frozen=True)
class AudioCheckResult:
    https_alive: bool
    http_alive: Optional[bool]  # https 生存時は未確認のため None
    content_type: Optional[str]
    content_length: Optional[int]


def check_audio(
    https_url: str,
    http_url: str,
    head_func: Callable[[str], HeadResult] = head,
    sleep_func: Callable[[float], None] = time.sleep,
) -> AudioCheckResult:
    """https 優先で生存確認し、死んでいた場合のみ http にフォールバックする。

    元の audio_url が最初から https の回では、フォールバック先が同一 URL に
    なるため確認しない(同じ URL への二重 HEAD を避ける)。その場合の
    http_alive は None(未確認)であり False(確認して死亡)と区別する。
    """
    https_result = head_func(https_url)
    if https_result.ok:
        return AudioCheckResult(
            https_alive=True,
            http_alive=None,
            content_type=https_result.content_type,
            content_length=https_result.content_length,
        )
    if https_url == http_url:
        return AudioCheckResult(
            https_alive=False,
            http_alive=None,
            content_type=None,
            content_length=None,
        )
    sleep_func(REQUEST_INTERVAL_SECONDS)
    http_result = head_func(http_url)
    # http で取れた length/type は同一パスの同一ファイルの実測値なので採用する
    # (拡張子からの推定より正確。https 復活時にもそのまま正しい値になる)
    return AudioCheckResult(
        https_alive=False,
        http_alive=http_result.ok,
        content_type=http_result.content_type,
        content_length=http_result.content_length,
    )
