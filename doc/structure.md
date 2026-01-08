# ソフトウェア構造 (Software Structure)

## 1. ディレクトリ構成
本プロジェクトのディレクトリ構成と各ファイル・フォルダの役割は以下の通りです。

```text
ffmpeg-voice-vox/
├── doc/                 # ドキュメント (本フォルダ)
│   ├── structure.md     # ソフトウェア構造
│   ├── specifications.md # 仕様書
│   └── control_logic.md # 制御内容
├── static/              # 静的ファイル (フロントエンド)
│   ├── css/
│   │   └── style.css    # Web UIのスタイル定義
│   └── js/
│       └── main.js      # Web UIの制御ロジック (API呼び出し、ポーリング)
├── templates/
│   └── index.html       # Web UIのメインテンプレート
├── tests/               # テストコード
├── output/              # 生成物 (WAV/SRT) の保存先 (自動生成)
└── server.py            # メインアプリケーション (Flaskサーバー)
```

## 2. システム構成図
本システムは、以下の3つの主要コンポーネントで構成されています。

1.  **Backend Server (`server.py`)**
    *   Python (Flask) 製のサーバーアプリケーション。
    *   外部からのJSONストリーム受信、データ解析、Voicevoxへのリクエスト、ファイル保存、クライアントへのAPI提供を行います。

2.  **Frontend Client (`index.html`, `main.js`)**
    *   Webブラウザ上で動作するユーザーインターフェース。
    *   設定の変更、ログの閲覧、生成音声の再生・削除、サーバーの状態監視を行います。

3.  **External Services**
    *   **Input Source (Whisper/FFmpeg)**: テキスト認識結果をJSON形式でストリーミング送信する外部プロセス（本アプリの入力元）。
    *   **Voicevox Engine**: 音声合成を行うローカルAPIサーバー（ポート50021で動作）。

## 3. コンポーネント間の連携
*   **Input -> Backend**: HTTP POST (`/`) によるストリーミング通信。
*   **Backend -> Voicevox**: HTTP POST (`/audio_query`, `/synthesis`) によるREST API呼び出し。
*   **Backend -> Client**: HTTP GET/POST (`/api/*`) によるREST API通信。Clientは定期的なポーリングで最新状態を取得します。
