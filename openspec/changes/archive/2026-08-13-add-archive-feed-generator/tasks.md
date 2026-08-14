# Tasks: セキュリティのアレ 過去回アーカイブフィード生成ツール

## 1. プロジェクト基盤

- [x] 1.1 パッケージ構成の作成(`src/` 配下に load / guid / diff / ledger / render / fetch / cli の空モジュール、`tests/` の骨組み。標準ライブラリのみ・依存追加なし)
- [x] 1.2 `references/` を .gitignore に追加し、ファンリポジトリの clone 手順を確認する
- [x] 1.3 実データのフィクスチャ採取(現行フィードの item 断片・ファン CSV の実レコード断片(S1/S2/S3 各数行、`&` 入りタイトル含む)を `tests/fixtures/` に保存)

## 2. 純粋モジュール: 入力と選別(load)

- [x] 2.1 CSV 読み込み(ヘッダ名アクセス・必須列アサート・recorded_date 不使用)を実装しテストする
- [x] 2.2 `url` からの p 番号抽出(`https://www.tsujileaks.com/?p=NNN` 厳密一致)を実装しテストする
- [x] 2.3 処理対象の選別と S2 除外の不変条件(除外行は season==2 のみ、S2 以外の除外・未知 season は fail-loud)を実装しテストする(正常分割・S3 で audio_url 空・未知 season の各ケース)

## 3. 純粋モジュール: 差分と台帳(diff / ledger / guid)

- [x] 3.1 フィード XML の解釈(item 0件の検出、全 guid の形式アサーション `^https?://www\.tsujileaks\.com/\?p=\d+$`、p 番号集合の抽出)を実装しテストする
- [x] 3.2 p 番号ベースの差分計算と「フィードに在るが CSV に無い p」の検出を実装しテストする
- [x] 3.3 台帳の読み込み・追記計算(未知 p のみ・p 昇順・冪等)・guid 食い違い検出(fail-loud)を実装しテストする
- [x] 3.4 guid 決定順位(台帳の観測値そのまま → `http://www.tsujileaks.com/?p=NNN` 合成)を実装し、全数に近い網羅でテストする

## 4. 純粋モジュール: レンダリング(render)

- [x] 4.1 item 生成(enclosure は常に https 書き換え URL・実 length/type、guid、pubDate の ISO 8601→RFC 1123 変換)を `xml.etree.ElementTree` で実装しテストする
- [x] 4.2 リンク切れ表現(タイトル接頭辞【音源リンク切れ】、description への検出日時・元 URL・http 取得可否の記録)を3ケース(https 生存/https 死・http 生/両方死)でテストする
- [x] 4.3 channel メタデータ(非公式と分かるタイトル・公式サイトへの link・生成日とファンリポジトリのコミットハッシュと本リポジトリ URL を含む説明文)を実装しテストする
- [x] 4.4 golden file テスト(固定入力 → 期待 XML 完全一致。`&` 入りタイトルの well-formed 検証を含む)

## 5. I/O と結線(fetch / cli)

- [x] 5.1 fetch: フィード GET と音源 HEAD(https→失敗時のみ http フォールバック、順次実行・間隔・明示 UA)を関数注入可能な形で実装し、手書き Fake でテストする
- [x] 5.2 cli: 引数解釈(CSV パス・出力パス・台帳パス)とパイプライン結線(load→feed 取得→台帳更新→diff→生存確認→render→書き出し)を実装する
- [x] 5.3 実行サマリ(フィード件数・処理対象・除外内訳・出力内訳・リンク切れ件数・台帳追記件数・CSV 未収載 p の警告)を実装しテストする
- [x] 5.4 ファンリポジトリのコミットハッシュ取得(references/ の git rev-parse)と channel 説明文への埋め込みを実装する

## 6. 結合確認と初回生成

- [x] 6.1 実データでの生成を実行し、サマリ(想定: フィード300件・出力42件・S2 除外45件・リンク切れ0件)と archive.xml を目視確認する
- [x] 6.2 guid 台帳の初回生成(現行フィード300件分)をコミットする
- [x] 6.3 再実行して冪等性(archive.xml の item 集合不変・台帳無変更)を確認する

## 7. ドキュメント

- [x] 7.1 README: 目的・非公式である旨・運用フロー(clone→生成→目視→配置→1回取り込み→将来の再実行)・出典と MIT ライセンス表記・references/ がバックアップを兼ねる旨
- [x] 7.2 README: 既知事項(S2 は動画連載のため対象外(@IT 連載インデックスへの案内)、合成 guid は歴史的推定、CSV 鮮度は Action 稼働依存で長期停止後はギャップがあり得る、音源サーバーは accept-ranges: none、フィード保持件数は設定値で可変)
- [x] 7.3 README: 他番組向け汎用レシピ(件数上限は設定値・ミラー確認は iTunes API・Wayback の限界・番組固有の一次資料・guid 同形式合成・差分のみ/再ホストしない/非公式明記・paged=2 の 200 に注意)
- [x] 7.4 PLAN.md を削除する(openspec ドキュメント群への吸収完了の確認後)
