# GitHub Actions 利用ガイド

## 概要
`.github/workflows/gemini-review.yml` は push をトリガーに、変更ファイルの抽出から Gemini でのレビュー生成、成果物コミットまでを自動化します。レビューはコード／OCR テキスト双方を扱い、失敗時はワークフローを明示的に失敗させます。

## 必要な設定
- `GEMINI_API_KEY`（必須）: Gemini API キー。未設定のままレビュー対象が存在するとワークフローは失敗します。
- `GEMINI_MODEL`（任意）: 使用モデルを上書きします。空や未設定の場合は `gemini-2.5-flash` を採用します。
- `docs/target-extensions.csv`: 監視する拡張子とプロンプトの対応表。ヘッダー付きフォーマット（`extension,base_prompt,custom_prompt`）を推奨します。
- `docs/instruction-review.md` と `docs/instruction-review-custom.md`: 既定のレビュープロンプト。拡張子別カスタムは `docs/` 配下に追加し、CSV で指定します。

## ワークフローの主なステップ
1. **チェックアウト**: `actions/checkout@v4` が再コミット用の認証情報を保持したままリポジトリを取得します。
2. **Python セットアップと依存導入**: Python 3.11 を使用し、`google-generativeai` `pyocr` `pillow` `pytest` をインストールします。
3. **Git 設定**: `core.quotepath=false` により日本語ファイル名をエスケープしません。
4. **対象拡張子の読み込み**: `scripts/load_extensions.py` が CSV を解析し、`tj-actions/changed-files` に渡す glob パターンを生成します。
5. **変更ファイルの抽出**: `tj-actions/changed-files@v45` が対象拡張子の変更を列挙します。`scripts/` や `docs/` などレビュー不要ディレクトリは除外済みです。
6. **ファイルパスの復元**: 変更があった場合のみ `scripts/decode_file_paths.py` が安全にパスを復元し、`decoded_files.txt` と `ocr_files_list.txt` を作成します。
7. **OCR 処理**: 画像が検知された場合、Tesseract を導入して `scripts/process_ocr.py` がテキスト化します。生成先は `ocr_outputs/` です。
8. **レビュー実行**: `scripts/run_reviews.py` がレビュー対象の有無を確認し、存在すれば Gemini を呼び出します。
   - 出力先は `REVIEW_BASE_DIR`（既定 `review`）配下の日付ディレクトリで、同日複数回は `_1` `_2` … を付与します。
   - `decoded_files.txt` は拡張子マップを有効にしてレビュー、`ocr_files_list.txt` は既定プロンプトでレビューします。
   - いずれかのファイルで例外が発生すると Markdown に詳細を書き出し、プロセスは非ゼロ終了します。
9. **成果物コミット**: レビューが 1 件以上生成された場合のみ `stefanzweifel/git-auto-commit-action@v5` が `files_to_commit` に指定されたディレクトリをコミット・プッシュします。OCR 出力も同様に別コミットで扱います。
10. **クリーンアップ**: 一時リスト（`decoded_files.txt`, `ocr_files_list.txt`）を削除します。

## 出力とログ
- `scripts/run_reviews.py` は `files_to_commit` と `review_count` を標準出力に書き、Actions の後続ステップが参照します。
- 標準エラーにはレビュー対象判定や生成件数、失敗時のトレースバックが出力されます。`🚨 レビュー失敗:` を目印にすると原因特定が容易です。
- 各レビュー結果は `review/<日付>[_番号]/<ファイル名>.md` に保存されます。内容にはモデル出力またはエラー詳細が含まれます。

## よくある調整ポイント
- **対象拡張子の更新**: `docs/target-extensions.csv` に追記・削除すると自動で監視対象が変わります。複数サフィックス（例: `.spec.ts`）も行単位で定義できます。
- **プロンプトの差し替え**: `docs/` 配下の Markdown を編集するだけで反映されます。拡張子ごとに別 Markdown を割り当てられます。
- **出力パス変更**: `REVIEW_BASE_DIR` を上書きすることで、レビュー結果の保存先を切り替えられます。
- **モデル切り替え**: `GEMINI_MODEL` に空でない文字列を設定すると `_resolve_model_name` により優先されます。

## トラブルシューティング
- **GEMINI_API_KEY が未設定**: レビュー対象がある状態で未設定だと `Error: GEMINI_API_KEY is not set` が表示され、ジョブが失敗します。Secrets を確認してください。
- **レビュー対象がゼロ**: いずれのリストも空の場合は「No files to review: skip Gemini API calls」と出力し、正常終了します。何もコミットされません。
- **Gemini API エラー**: 各レビュー Markdown に固定文と併せてエラー内容とトレースバックが保存されます。Gemini 側のレスポンスで「model name format」などが出た場合は `GEMINI_MODEL` の値を確認してください。
- **OCR 関連エラー**: 画像があるのにテキストが生成されない場合、`scripts/process_ocr.py` が非ゼロで終了しステップが失敗します。`ocr-process` ログを確認し、Tesseract のインストール状態を見直してください。
