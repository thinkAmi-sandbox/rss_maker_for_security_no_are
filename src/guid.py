"""アーカイブ item の guid 決定。

優先順位:
1. 台帳にその p 番号の観測記録があれば、記録された文字列をそのまま使う
2. なければ http://www.tsujileaks.com/?p=NNN を合成する

http で合成する根拠: フィード最古付近の44件(p=491〜846)の guid が例外なく
http であり、2017年の Wayback スナップショットでも http だったこと。合成値は
「当時の実 guid と完全一致する保証」ではなく、歴史的証拠に基づく最善の推定。
"""


def resolve_guid(article_number: int, ledger_entries: dict) -> str:
    known = ledger_entries.get(article_number)
    if known is not None:
        return known.guid
    return synthesize_guid(article_number)


def synthesize_guid(article_number: int) -> str:
    return f"http://www.tsujileaks.com/?p={article_number}"
