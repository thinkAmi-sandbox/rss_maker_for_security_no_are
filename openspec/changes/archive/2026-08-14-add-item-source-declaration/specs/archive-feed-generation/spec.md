# Spec Delta: archive-feed-generation(全 item への出典宣言)

## MODIFIED Requirements

### Requirement: RSS 2.0 の生成

ツールは出力対象の回を標準 RSS 2.0(UTF-8)の `archive.xml` として生成しなければならない(MUST)。各 item は以下を満たさなければならない(MUST):

- `<enclosure>` を必ず持つ。`url` 属性は生存確認の結果に依存せず、常に `audio_url` を https に書き換えた URL とする(出力の冪等性のため)。`length` / `type` には生存確認で取得した実値を入れる(取得できなければ `length` は省略する)
- `<guid isPermaLink="false">` を必ず持つ(値の決定は guid-ledger 仕様に従う)
- `<pubDate>` は CSV の `published_datetime`(ISO 8601)を RFC 1123 形式に変換した値とする
- リンク切れ検出時のみ `<title>` の接頭辞に `【音源リンク切れ】` を付ける(接尾辞ではなく接頭辞。一覧表示で切り詰められないため)
- item の末尾(`<description>` の後)に、出典宣言 `<source url="...">` を必ず1つ持つ。`url` 属性は**このツールが現行フィードの取得・差分計算に実際に使った URL と同一の文字列**とし(既定では公式フィード URL)、cli から render へ値を引き回して設定する。render 側でフィード URL の定数を二重に持ってはならない(MUST NOT)。要素テキストは公式の番組名 `セキュリティのアレ`(出典フィード側の channel title。アーカイブ自身の channel title を流用してはならない(MUST NOT))
- 出典宣言として `atom:link rel="self"` を公式フィードに向けて使用してはならない(MUST NOT)(フィード移転検出として解釈するクライアントが購読 URL を書き換える恐れがあるため)
- XML は文字列連結ではなく XML API で構築する(タイトル中の `&` 等のエスケープ漏れを構造的に防ぐため)

channel メタデータは、非公式であることが一目で分かるタイトル、公式サイトへの `<link>`、生成日・参照したファンリポジトリのコミットハッシュ・本リポジトリ URL を含む説明文を持たなければならない(MUST)。コミットハッシュは、リモート取得ではダウンロード時に確定した sha、ローカル指定ではその CSV を追跡している git リポジトリの HEAD とする。追跡を確認できない場合(git 管理外へのコピー等)は `unknown` を記録し、無関係なリポジトリのハッシュを出典として記録してはならない(MUST NOT)。

#### Scenario: 通常の item の生成

- **WHEN** リンク切れのない回をレンダリングする
- **THEN** enclosure(https URL・実 length・実 type)、guid、RFC 1123 の pubDate、元のままの title、`<source>`(差分計算に使った URL・公式番組名)を持つ item が出力される

#### Scenario: 特殊文字を含むタイトル

- **WHEN** タイトルに `&` や `<` を含む回をレンダリングする
- **THEN** 出力 XML は well-formed であり、パースすると元の文字列が復元される

#### Scenario: 生成物の再現性

- **WHEN** 同じ CSV・同じフィード状態・同じ生存確認結果で2回生成する
- **THEN** 2つの archive.xml の item 集合・guid・enclosure URL は完全に一致する(生成日時などチャンネルメタの時刻情報のみ異なってよい)

#### Scenario: 全 item への出典宣言

- **WHEN** archive.xml を生成する
- **THEN** すべての item が `<source url>` を持ち、その url は全 item で同一である

#### Scenario: フィード URL 差し替え時の追随

- **WHEN** `--feed-url` に既定以外の URL を指定して生成する
- **THEN** 出力の全 item の `<source url>` は指定した URL と同一の文字列になる(差分計算に使った URL と宣言が常に一致する)
