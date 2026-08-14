# Proposal: セキュリティのアレ 過去回アーカイブフィード生成ツール

## Why

ポッドキャスト「セキュリティのアレ」の公式 RSS(`https://www.tsujileaks.com/?feed=podcast`)は最新300件のみを配信しており、押し出された過去回(現行シリーズ第1〜14回+雑談2本、旧シリーズ S1 全26回)をサーバーから取得する手段がない(ページング・RFC 5005 不使用、Spotify/Apple も同一フィードのミラー)。一方、音源ファイル自体は公式サーバーに現存し https で取得できる(全42回分の生存を HEAD で実測確認済み)。

この番組を新しく聴き始める人が、取りこぼした過去回を自分のポッドキャストプレイヤーに1回だけ取り込めるよう、ファンサイトリポジトリの公開データ(MIT ライセンス)から標準 RSS 2.0 のアーカイブフィード(`archive.xml`)を生成する、この番組専用のツールを作る。

## What Changes

- ファンリポジトリ [BerandaMegane/Security-no-ARE-words](https://github.com/BerandaMegane/Security-no-ARE-words) の自動更新 CSV(`source/_static/セキュリティのアレ_放送回リスト_自動更新.csv`)を入力に、現行フィードとの差分(=現在配信されていない回のみ)を RSS 2.0 として出力する CLI を新規作成する
- 公式フィードで観測した guid を記録する **guid 台帳**(`p,guid,first_seen` の CSV)をリポジトリにコミットし、生成コマンドの一部として毎回更新する。将来押し出される回には観測済みの実 guid を使えるようにする
- 音源 URL の生存確認(HEAD、順次・間隔付き・明示 UA)を行い、リンク切れはタイトル接頭辞【音源リンク切れ】と description への記録で明示する
- README に運用フロー・出典・非公式である旨・S2(@IT 動画時代)の案内・他番組向けの汎用レシピを記載する

## Capabilities

### New Capabilities

- `archive-feed-generation`: ファン CSV と現行フィードから差分アーカイブ RSS(archive.xml)を生成するパイプライン全体。入力検証(S2 除外の不変条件)、p 番号ベースの差分計算、fail-loud ガード、音源生存確認、RSS 2.0 レンダリング、実行サマリ表示を含む
- `guid-ledger`: 公式フィードで観測した guid の蓄積台帳。追記のみの更新規則、既知 p 番号での guid 食い違い検出(fail-loud)、アーカイブ guid の決定順位(台帳優先→http 合成)を含む

### Modified Capabilities

(なし — 新規リポジトリのため既存仕様はない)

## Impact

- **新規コード**: Python(標準ライブラリのみ、mise で 3.14 系固定)のモジュール群と CLI。テストは unittest
- **リポジトリ内データ**: `data/guid_ledger.csv`(生成のたびに追記され、コミット対象)
- **外部依存**: ファンリポジトリの clone(`references/`、.gitignore 対象、バックアップ兼用)と、実行時の公式フィード GET・音源 HEAD。パッケージ依存はゼロ
- **配布物**: `archive.xml`(利用者がその時点で生成する使い捨てフィード。永続公開はしない)
- **関連システム**: podcast_player(別リポジトリ)への注入は本リポジトリの関知外だが、guid 契約(`(feedId, guid)` の文字列等価)と enclosure 必須制約を出力仕様として守る
