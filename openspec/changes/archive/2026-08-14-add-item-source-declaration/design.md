# Design: 全 item への出典宣言(`<source>`)

## Context

podcast_player は archive.xml を既存購読へ一度きり注入する際、「XML の全 item の `<source url>` が同一で、かつ注入先購読の feedUrl(DB 保存値)と完全一致(trim 後)」を検証し、1つでも欠落・不一致なら全体を拒否する(部分取り込みなし)。比較の両辺が独立した出所(XML と DB)を持つため、引数の取り違えは必ず不一致として現れる。アプリは「宣言が item の中身と本当に対応しているか」までは検証しない — その保証は本ツールの構造(差分計算に使った URL をそのまま書く)とテストが担う。

事前確認済みの事実(2026-08-14):

- 公式フィードの channel title は正確に `セキュリティのアレ`(RSS 2.0 の「source テキスト = 出典チャンネルの title」に一致)
- 公式フィード300 item に `<source>` は存在しない(「公式フィード自身は注入検証で拒否される」設計の前提)

## Goals / Non-Goals

**Goals:**

- 全 item への `<source url="...">セキュリティのアレ</source>` の追加
- 「宣言 = 差分計算に実際に使った URL」を、定数の共有ではなく**値の引き回し**で構造的に保証する

**Non-Goals:**

- guid・台帳・差分・バッジ・enclosure・channel メタ等、既存出力仕様の変更(一切なし)
- podcast_player 側の検証実装(先方リポジトリの管轄)

## Decisions

### D1. 出典情報は ArchiveItem ではなく build_feed / build_item_element の引数で渡す

`<source>` の値は全 item で共通のフィードレベルの単一値。frozen dataclass の `ArchiveItem` にフィールドを足すと同じ値を42回複製することになるため、`build_feed(channel, items, source_url, source_title)` → `build_item_element(item, source_url, source_title)` の引数として渡す(依頼はどちらも許容。意味に合う方を選択)。

### D2. url は cli から引き回す(render で定数を持たない)

`cli.run()` の `args.feed_url` — フィード取得と差分計算に実際に使われた値 — をそのまま render へ渡す。render 側で `fetch.FEED_URL` を import すると、`--feed-url` 差し替え時に「取得に使った URL」と「宣言した URL」が乖離する定数二重持ちの罠になる。`--feed-url` 追随のテスト(tasks 参照)がこの混入を検出する。

**運用上の含意**: アプリの検証は購読登録時の feedUrl 文字列との完全一致なので、購読が既定と異なる文字列(www なし等)で登録されている場合、既定生成の archive.xml は拒否される(取り違え検出として意図どおり)。復旧は「`--feed-url` に購読と同じ文字列を渡して再生成」であり、引き回し設計により取得・差分・宣言のすべてが自動的にその URL で揃う。

### D3. source テキストは cli の定数 `OFFICIAL_TITLE`(フィードから動的抽出しない)

**代替案として棄却**: 取得したフィードの channel title を抽出して使えば公式の改名にも追随するが、検証対象外の表示文字列のために `diff.parse_feed` の戻り値を変えることになり、guid・台帳・差分のテストへ波及する(依頼 §5「既存テストは変更不要のはず」と矛盾)。テキストは人間向け表示であり、実フィードの title と一致する定数で十分。channel の title(「〜過去回アーカイブ(非公式)」)の流用は RSS 2.0 の意味論(source = 出典側の名前)に反するため禁止(spec に明記)。

### D4. 挿入位置は item 末尾(description の後)に固定

RSS 2.0 上は位置自由だが、golden fixture の安定のため固定する。既存の builder の要素追加順の最後に足すだけで自然に満たされる。

### D5. `atom:link rel="self"` は使わない(棄却済み代替案の記録)

rel="self" は「この文書自身の URL」の意味であり、フィード移転検出として解釈するクライアントが購読 URL を公式フィードへ書き換える恐れがある。archive.xml を別番組として購読する利用者への実害となるため、依頼 §2.4 のとおり禁止(spec に MUST NOT で明記)。

## Risks / Trade-offs

- **[公式番組名の改名で source テキストが古くなる]** → 検証対象外の表示文字列であり実害なし。改名時に定数を更新すれば足りる(D3 のトレードオフとして受容)
- **[一般プレイヤーでの表示]** → `<source>` は RSS 2.0 標準要素。無視するか出典として表示するだけで、別番組購読の利用者に影響しない(依頼 §8)

## Migration Plan

実装 → テスト(golden 更新・`--feed-url` 追随)→ README 追記 → archive.xml 再生成 → 既存 Gist の `are.xml` を更新(同一 Gist なら raw URL 不変。CDN キャッシュ max-age=300 のため反映まで最大5分)。

## Open Questions

なし(podcast_player 側の依頼文書と探索セッションで解決済み)
