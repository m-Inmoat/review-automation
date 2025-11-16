# Gemini Review Automation Design

このドキュメントは GitHub Actions ワークフロー `gemini-review.yml` と周辺スクリプトの責務・連携を整理した設計メモです。

## ワークフロー全体像

- **起点**: `.github/workflows/gemini-review.yml`
  - トリガーは push のみ。全ブランチで発火し、結果も同一ブランチにコミットします。
  - `tj-actions/changed-files` で変更ファイルを抽出し、`scripts/decode_file_paths.py` に渡してパス復元と拡張子フィルタを行います。
  - `decoded_files.txt`（コード）と `ocr_files_list.txt`（画像派生テキスト）を生成し、`scripts/run_reviews.py` に渡します。
  - `GEMINI_API_KEY`・`GEMINI_MODEL`・`REVIEW_BASE_DIR` などの環境変数をステップ単位で設定します。

## Python スクリプトの役割

### `scripts/load_extensions.py`
- `docs/target-extensions.csv` を読み込み、`tj-actions/changed-files` に渡す glob パターンを生成します。
- 複数サフィックス（`.spec.ts` など）も CSV で定義可能です。空行やコメントはスキップします。

### `scripts/decode_file_paths.py`
- `changed-files` の出力（カンマ区切り）を受け取り、以下を実施します。
  - バックスラッシュエスケープや UTF-8 を復元して実パスを再現。
  - 拡張子パターンに一致するものを `decoded_files.txt` へ出力。
  - OCR 対象の拡張子（PNG/JPG 等）は `ocr_files_list.txt` に追記します。

### `scripts/process_ocr.py`
- 画像リストを受け取り、Tesseract を使って OCR 文字起こしを実施します。
- 出力は `ocr_outputs/` 配下の `.txt`。入力があるのに出力が 0 件の場合は非ゼロ終了してワークフロー失敗を促します。

### `scripts/gemini_cli_wrapper.py`
- Gemini API を呼び出す CLI。
- `_resolve_model_name` が明示値→環境変数→デフォルトの優先順でモデルを決定します。
- プロンプト Markdown をアップロードし、`.prompt_upload_cache.json` にキャッシュして同ワークフロー内で再利用します（キャッシュファイルはリポジトリにコミットされません）。
- `batch-review` はファイルごとに拡張子マップを評価し、適切なプロンプトパーツを組み合わせて `generate_content` を呼び出します。
- 例外が発生した場合は詳しいトレースバックを stderr とレビュー Markdown に書き込み、非ゼロ終了で上位に通知します。

### `scripts/run_reviews.py`
- 全体オーケストレーター。レビュー対象が無ければ早期終了し、`GEMINI_API_KEY` も要求しません。
- 出力ディレクトリは `REVIEW_BASE_DIR`（既定 `review`）配下の日付ディレクトリで、同日内の再実行は `_1`, `_2` で重複回避します。
- `decoded_files.txt` を拡張子マップありでレビューし、`ocr_files_list.txt` が存在すれば既定プロンプトのみで再度レビューを実施します。
- 生成した Markdown 件数をカウントし、GitHub Actions の `files_to_commit` / `review_count` 出力として公開します。
- 失敗が一つでもあれば直ちに非ゼロ終了し、ワークフローを失敗扱いにします。

## プロンプト管理 (`docs/target-extensions.csv`)

- 各行は `拡張子, ベースプロンプト Markdown, カスタムプロンプト Markdown` の形式です。ベース／カスタムは省略可で、空の場合はデフォルトプロンプトが使われます。
- `gemini_cli_wrapper.py` は CSV 参照のほか、`docs/` 配下の Markdown を包括的にアップロード対象に含めます。これにより、CSV 未指定の追加ドキュメントもアップロード済みになります。
- アップロードした Markdown の File ID は `.prompt_upload_cache.json` に保存し、同一ワークフロー内で再アップロードを回避します。キャッシュ破損時は再アップロードして復旧します。

## 処理フロー概要

1. Actions が対象拡張子を読み込み、変更ファイルと画像ファイルを抽出します。
2. `decode_file_paths.py` が `decoded_files.txt` / `ocr_files_list.txt` を生成します。
3. 必要に応じて OCR を実行し、テキスト化された結果を `run_reviews.py` がレビュー対象として扱います。
4. `run_reviews.py` がディレクトリを作成し、`gemini_cli_wrapper.py` を通じてコードレビューおよび OCR レビューを実施します。
5. 各レビュー Markdown には成功時の出力、失敗時のエラーログが記録されます。失敗が含まれるとプロセスが非ゼロ終了し、ワークフロー全体が失敗になります。
6. 正常終了かつレビューが生成された場合のみ、`files_to_commit` で指定されたディレクトリが自動コミットされます。

この構成により、拡張子ごとの専用プロンプトと詳細な失敗レポートを備えた自動レビューを継続的に実行できます。