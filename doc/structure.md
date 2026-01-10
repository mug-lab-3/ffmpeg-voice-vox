# ソフトウェア構造 (Software Structure)

## 1. ディレクトリ構成
本プロジェクトのディレクトリ構成と各ファイル・フォルダの役割は以下の通りです。

```text
ffmpeg-voice-vox/
├── run.py                 # アプリケーション起動スクリプト (エントリーポイント)
├── config.json            # ユーザー設定ファイル (初回起動時に自動生成)
├── doc/                   # ドキュメント (本フォルダ)
│   ├── structure.md       # ソフトウェア構造
│   ├── specifications.md  # 仕様書
│   └── control_logic.md   # 制御内容
├── logs/                  # ログファイル保存先
│   └── app.log            # アプリケーションログ
├── app/                   # アプリケーションパッケージ
│   ├── __init__.py        # Flaskアプリケーションファクトリ
│   ├── config.py          # 設定管理モジュール
│   ├── core/              # ビジネスロジック
│   │   ├── voicevox.py    # VoiceVox APIクライアント
│   │   ├── audio.py       # 音声ファイル管理・再生制御
│   │   └── processor.py   # ストリーム処理・オーケストレーション
│   └── web/
│       └── routes.py      # Flaskルート定義 (APIエンドポイント)
├── static/                # 静的ファイル (フロントエンド)
│   ├── css/
│   │   └── style.css      # Web UIのスタイル定義
│   └── js/
│       └── main.js        # Web UIの制御ロジック
├── templates/
│   └── index.html         # Web UIのメインテンプレート
├── output/                # 生成物 (WAV/SRT) の保存先
└── tests/                 # テストコード
```

## 2. システム構成図
本システムは、以下の3つの主要コンポーネントで構成されています。

1.  **Backend Server (`run.py` / `app/`)**
    *   Python (Flask) 製のサーバーアプリケーション。
    *   機能を `app.core` (ロジック) と `app.web` (API) に分離し、保守性を高めています。
    *   設定は `config.json` から読み込み、ログは files `logs/` に保存します。

2.  **Frontend Client (`index.html`, `main.js`)**
    *   Webブラウザ上で動作するユーザーインターフェース。
    *   設定の変更、ログの閲覧、生成音声の再生・削除、サーバーの状態監視を行います。

3.  **External Services**
    *   **Input Source (Whisper/FFmpeg)**: テキスト認識結果をJSON形式でストリーミング送信する外部プロセス。
    *   **Voicevox Engine**: 音声合成を行うローカルAPIサーバー（ポート50021で動作）。

## 3. コンポーネント間の連携
*   **Input -> Backend**: HTTP POST (`/`) によるストリーミング通信。`app.core.processor` が処理します。
*   **Backend -> Voicevox**: HTTP POST によるREST API呼び出し。`app.core.voicevox` が担当します。
*   **Backend -> Client**: HTTP GET/POST (`/api/*`) によるREST API通信。`app.web.routes` がハンドリングします。
