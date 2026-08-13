import unittest
import urllib.error

from src.fetch import (
    FAN_COMMITS_API_URL,
    USER_AGENT,
    AudioCheckResult,
    HeadResult,
    check_audio,
    fetch_fan_csv,
    fetch_feed,
    head,
)


class FakeResponse:
    """urlopen の戻り値を模す手書き Fake(コンテキストマネージャ)。"""

    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self._headers = headers or {}
        self._body = body

    @property
    def headers(self):
        return self

    def get(self, name, default=None):
        return self._headers.get(name, default)

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    """渡された Request を記録し、指定した応答(または例外)を返す。"""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.error is not None:
            raise self.error
        return self.response


class FakeHead:
    """URL ごとの応答を差し替える手書き Fake。呼び出しを記録する。"""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses[url]


class FakeSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


HTTPS = "https://www.tsujileaks.com/media/a.m4a"
HTTP = "http://www.tsujileaks.com/media/a.m4a"


class HeadRequestTest(unittest.TestCase):
    """実 HTTP リクエスト構築部の検証(仕様: 明示的な User-Agent は MUST)。"""

    def test_sends_head_with_explicit_user_agent(self):
        opener = FakeOpener(
            FakeResponse(
                headers={"Content-Type": "audio/mp4", "Content-Length": "123"}
            )
        )
        result = head(HTTPS, opener=opener)
        self.assertEqual(len(opener.requests), 1)
        req = opener.requests[0]
        self.assertEqual(req.get_method(), "HEAD")
        self.assertEqual(req.get_header("User-agent"), USER_AGENT)
        self.assertEqual(
            result,
            HeadResult(ok=True, content_type="audio/mp4", content_length=123),
        )

    def test_missing_content_length_is_none(self):
        opener = FakeOpener(FakeResponse(headers={"Content-Type": "audio/mp4"}))
        result = head(HTTPS, opener=opener)
        self.assertEqual(result.ok, True)
        self.assertIsNone(result.content_length)

    def test_non_200_status_is_not_ok(self):
        opener = FakeOpener(FakeResponse(status=204))
        self.assertEqual(head(HTTPS, opener=opener), HeadResult(ok=False))

    def test_http_error_is_not_ok(self):
        opener = FakeOpener(
            error=urllib.error.HTTPError(HTTPS, 404, "Not Found", None, None)
        )
        self.assertEqual(head(HTTPS, opener=opener), HeadResult(ok=False))

    def test_network_error_is_not_ok(self):
        opener = FakeOpener(error=urllib.error.URLError("timeout"))
        self.assertEqual(head(HTTPS, opener=opener), HeadResult(ok=False))


class SequenceOpener:
    """呼び出し順に応答を返す Fake。Request を記録する。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        return self.responses.pop(0)


class FetchFanCsvTest(unittest.TestCase):
    def test_pins_download_to_resolved_sha(self):
        """先に main の sha を確定し、その sha の raw URL から取得する。"""
        sha = "b3f57975399dd933665e51e72d46ec2371c1e793"
        opener = SequenceOpener(
            [
                FakeResponse(body=('{"sha": "%s"}' % sha).encode("utf-8")),
                FakeResponse(body="season,num\n3,1\n".encode("utf-8")),
            ]
        )
        text, got_sha = fetch_fan_csv(opener=opener)
        self.assertEqual(got_sha, sha)
        self.assertEqual(text, "season,num\n3,1\n")
        # 1リクエスト目: commits API、2リクエスト目: sha 固定の raw URL
        self.assertEqual(opener.requests[0].full_url, FAN_COMMITS_API_URL)
        raw_url = opener.requests[1].full_url
        self.assertIn(f"/{sha}/", raw_url)
        self.assertIn("raw.githubusercontent.com/BerandaMegane", raw_url)
        self.assertIn("source/_static/", raw_url)
        self.assertNotIn("/main/", raw_url)  # main 直指定ではなく sha 固定
        # 日本語ファイル名は URL エンコードされている
        self.assertNotIn("セキュリティ", raw_url)
        self.assertIn("%E3%82%BB", raw_url)
        # どちらのリクエストも明示 UA
        for req in opener.requests:
            self.assertEqual(req.get_header("User-agent"), USER_AGENT)


class FetchFeedTest(unittest.TestCase):
    def test_sends_explicit_user_agent_and_decodes_utf8(self):
        opener = FakeOpener(FakeResponse(body="<rss>アレ</rss>".encode("utf-8")))
        text = fetch_feed("https://www.tsujileaks.com/?feed=podcast", opener=opener)
        self.assertEqual(text, "<rss>アレ</rss>")
        req = opener.requests[0]
        self.assertEqual(req.get_header("User-agent"), USER_AGENT)
        self.assertEqual(req.get_method(), "GET")


class CheckAudioTest(unittest.TestCase):
    def test_https_alive_skips_http(self):
        head = FakeHead(
            {HTTPS: HeadResult(ok=True, content_type="audio/mp4", content_length=100)}
        )
        sleep = FakeSleep()
        result = check_audio(HTTPS, HTTP, head_func=head, sleep_func=sleep)
        self.assertEqual(
            result,
            AudioCheckResult(
                https_alive=True,
                http_alive=None,
                content_type="audio/mp4",
                content_length=100,
            ),
        )
        # https で生きていれば http への問い合わせも待機も発生しない
        self.assertEqual(head.calls, [HTTPS])
        self.assertEqual(sleep.calls, [])

    def test_https_dead_falls_back_to_http(self):
        head = FakeHead(
            {
                HTTPS: HeadResult(ok=False),
                HTTP: HeadResult(ok=True, content_type="audio/mp4", content_length=1),
            }
        )
        sleep = FakeSleep()
        result = check_audio(HTTPS, HTTP, head_func=head, sleep_func=sleep)
        self.assertEqual(result.https_alive, False)
        self.assertEqual(result.http_alive, True)
        # http で取れた実測値は同一ファイルのものとして採用する
        self.assertEqual(result.content_type, "audio/mp4")
        self.assertEqual(result.content_length, 1)
        self.assertEqual(head.calls, [HTTPS, HTTP])
        self.assertEqual(len(sleep.calls), 1)  # フォールバック前に間隔を空ける

    def test_both_dead(self):
        head = FakeHead({HTTPS: HeadResult(ok=False), HTTP: HeadResult(ok=False)})
        result = check_audio(HTTPS, HTTP, head_func=head, sleep_func=FakeSleep())
        self.assertEqual(result.https_alive, False)
        self.assertEqual(result.http_alive, False)

    def test_https_origin_dead_skips_identical_fallback(self):
        """元から https の音源: 同一 URL への二重 HEAD をせず、未確認(None)とする。"""
        head = FakeHead({HTTPS: HeadResult(ok=False)})
        sleep = FakeSleep()
        result = check_audio(HTTPS, HTTPS, head_func=head, sleep_func=sleep)
        self.assertEqual(result.https_alive, False)
        self.assertIsNone(result.http_alive)  # False(確認して死亡)ではない
        self.assertEqual(head.calls, [HTTPS])  # HEAD は1回だけ
        self.assertEqual(sleep.calls, [])


if __name__ == "__main__":
    unittest.main()
