# Tasks: 全 item への出典宣言(`<source>`)

## 1. 実装

- [x] 1.1 render: `build_feed` / `build_item_element` に出典フィード URL・番組名の引数を追加し、item 末尾(description の後)に `<source url="...">番組名</source>` を出力する(ElementTree で構築)
- [x] 1.2 cli: `OFFICIAL_TITLE` 定数(`セキュリティのアレ`)を追加し、`args.feed_url` と併せて render へ引き回す(render 側でフィード URL 定数を import しない)

## 2. テスト

- [x] 2.1 test_render: golden fixture を更新し、全 item に `<source>` があること・url が指定値と一致すること・テキストが番組名であることを検査する
- [x] 2.2 test_cli: `--feed-url` を既定以外に差し替えて実行したとき、出力の全 item の `<source url>` がその値に追随することを検査する(定数二重持ちの混入検出)
- [x] 2.3 既存テスト(guid・台帳・差分)が無変更のまま全通過することを確認する

## 3. ドキュメント

- [x] 3.1 README: フィード形式説明に `<source>` の存在と意味(出典宣言。podcast_player の取り込み検証が参照する)を追記する

## 4. 再生成と配信

- [x] 4.1 archive.xml を再生成し、全42 item に `<source url="https://www.tsujileaks.com/?feed=podcast">セキュリティのアレ</source>` が入っていることを目視確認する
- [x] 4.2 既存 Gist(a30e72ff057e4fcbee9da2d1db4e3f7b)の `are.xml` を更新し、raw URL から取得して反映を確認する(CDN キャッシュのため最大5分待つ)
