# Proposal: 全 item への出典宣言(`<source>`)の追加

## Why

podcast_player(取り込み側)は archive.xml を既存購読へ一度きり注入する経路を実装予定であり、その際に最も起きやすい事故「コマンド引数ペアの取り違え」(別番組の購読にアーカイブを注入する/アレの購読に別の XML を注入する)を機械的に拒否したい。そのために各 item が「自分はどのフィード由来か」を申告し、アプリ側で注入先購読の feedUrl との完全一致を検証できるようにする(podcast_player 側からの仕様変更依頼、2026-08-14 受領)。

## What Changes

- 出力するすべての `<item>` に RSS 2.0 標準の `<source url="...">` 要素を1つ追加する(独自タグは発明しない)
- `url` 属性は **cli が実際にフィード取得・差分計算に使った URL(`--feed-url`、既定は公式フィード URL)をそのまま引き回した値**とする。render 側で URL 定数を二重に持たない(「宣言 = 差分計算に使った URL」の契約を値の引き回しで構造的に保証)
- 要素テキストは公式の番組名 `セキュリティのアレ`(定数)。RSS 2.0 仕様の「source のテキスト = 出典チャンネルの title」に一致することを実フィードで確認済み。アーカイブ自身の channel title は流用しない
- guid・台帳・差分・バッジ・enclosure など既存の出力仕様は一切変更しない
- README にフィード形式(`<source>` の存在と意味)を追記する

## Capabilities

### New Capabilities

(なし)

### Modified Capabilities

- `archive-feed-generation`: 要件「RSS 2.0 の生成」に、全 item への `<source>` 出力(url は差分計算に使った URL と同一文字列・テキストは公式番組名・挿入位置は item 末尾)を追加する

## Impact

- **コード**: `src/render.py`(要素追加・出典情報の受け口)、`src/cli.py`(番組名定数・`args.feed_url` の引き回し)のみ。diff / ledger / guid / load / fetch は無変更
- **テスト**: golden fixture の更新、全 item の `<source>` 検査、`--feed-url` 差し替え時の追随テスト(定数二重持ちの混入検出)。既存の guid・台帳・差分のテストは無変更
- **配信**: 変更後に archive.xml を再生成し、既存 Gist(`are.xml`)を更新する(raw URL は不変)
- **互換性**: `<source>` は RSS 2.0 標準要素であり、一般のプレイヤーは無視するか出典表示に使うだけ。別番組として購読する利用者への影響なし。`<source>` を持たない通常の RSS(公式フィード自身を含む。公式300件に `<source>` が無いことは実測確認済み)が podcast_player の注入検証で拒否されるのは意図した挙動
