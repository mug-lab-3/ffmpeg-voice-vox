# FFmpeg Voicevox Integration

本プロジェクトは、FFmpeg + Whisperなどからの音声認識結果(JSON)を受け取り、VOICEVOXを使用して合成音声を作成し、さらにDaVinci Resolveへの自動取り込み（音声および字幕）をシームレスに行うためのアプリケーションです。

## 主な機能

*   **音声合成**: VOICEVOXエンジンと連携し、高品質な合成音声を生成。
*   **DaVinci Resolve連携**: 生成された音声と字幕（テキスト）を、実行中のDaVinci Resolveのタイムラインへ自動挿入。
*   **Web UI**: 直感的なインターフェースで、生成履歴の管理（再生・修正・再挿入）や設定変更が可能。
*   **インテリジェントな管理**: 
    *   重複起動防止機能（既存プロセスの自動終了）。
    *   利用可能なポートの自動選択。
    *   ブラウザの自動起動。
    *   アクティビティ監視によるオートシャットダウン機能。
*   **マルチプラットフォーム対応**: WindowsおよびmacOSの両方で動作。

## 開発環境構築

### 必須要件
*   **OS**: Windows / macOS
*   **Python**: 3.x
*   **VOICEVOX**: 音声合成エンジン（エディタまたはエンジン）が起動していること。
*   **DaVinci Resolve**: 連携機能を使用する場合、DaVinci Resolveが起動しており、スクリプトAPIが有効であること。

### セットアップ手順

1.  **依存ライブラリのインストール**
    ```powershell
    pip install -r requirements.txt
    ```

2.  **VOICEVOXの準備**
    VOICEVOXを起動してください。デフォルトでは `http://127.0.0.1:50021` を使用します（`config.json` で変更可能）。

## 実行方法

以下のコマンドを実行してアプリケーションを起動します。
```powershell
python voicevox_controller.py
```
起動後、ブラウザが自動的に開き、管理画面が表示されます。

## プロジェクト構成

*   `voicevox_controller.py`: アプリケーションのエントリーポイント。
*   `app/`: コアロジック、API、Web UI のソースコード。
*   `static/` / `templates/`: フロントエンド資産。
*   `config.json`: ユーザー設定。
*   `data/`: 生成された音声ファイルや履歴データベース（SQLite）。
*   `doc/specification/`: 詳細な仕様ドキュメント。

詳細については、`doc/` フォルダ内の仕様書を参照してください。
