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

#### 基本環境
*   **OS**: Windows / macOS
*   **Python**: 3.x

#### 外部ツール・モジュール

##### FFmpeg
*   **用途**: 音声ファイルの変換・処理
*   **公式サイト**: [https://ffmpeg.org/](https://ffmpeg.org/)
*   **ダウンロード**: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
*   **インストール**: 任意のディレクトリに展開し、そのディレクトリを`config.json`の`ffmpeg_path`で指定してください。

##### Whisper C++ (GGML) モデル
*   **用途**: 音声認識(文字起こし)
*   **GitHubリポジトリ**: [https://github.com/ggerganov/whisper.cpp](https://github.com/ggerganov/whisper.cpp)
*   **モデルファイル**: 
    *   推奨モデル (スペック・用途に合わせて選択): 
        *   `ggml-large-v3-turbo.bin` (**標準推奨**: 精度はv2相当、速度は飛躍的に向上。VRAM 6GB以上推奨)
        *   `ggml-large-v3.bin` (**最高精度**: 処理時間は長いが最も正確。VRAM 10GB以上推奨)
        *   `ggml-small.bin` (**低スペック/省メモリ**: VRAM 2GB程度の環境やCPU処理向け)
    *   **直接ダウンロード**: 
        *   [ggml-large-v3-turbo.bin (Hugging Face)](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin)
        *   [ggml-large-v3.bin (Hugging Face)](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin)
        *   [ggml-small.bin (Hugging Face)](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin)
        *   リポジトリ: [ggerganov/whisper.cpp (Hugging Face)](https://huggingface.co/ggerganov/whisper.cpp/tree/main)
*   **設定**: ダウンロードしたモデルファイルのパスを`config.json`の`model_path`で指定してください。

##### VAD (Voice Activity Detection) モデル
*   **用途**: 音声区間検出(Sileroモデルを使用、Whisper C++で使用)
*   **GitHubリポジトリ**: [https://github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)
*   **モデルファイル**: 
    *   推奨モデル: `ggml-silero-v6.2.0.bin` (GGML形式、Whisper C++用)
    *   **直接ダウンロード**: 
        *   [ggml-silero-v6.2.0.bin (Hugging Face)](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin)
        *   リポジトリ: [ggml-org/whisper-vad](https://huggingface.co/ggml-org/whisper-vad)
*   **設定**: ダウンロードしたGGMLファイルのパスを`config.json`の`vad_model_path`で指定してください。

##### VOICEVOX
*   **用途**: 音声合成エンジン
*   **公式サイト**: [https://voicevox.hiroshiba.jp/](https://voicevox.hiroshiba.jp/)
*   **GitHubリポジトリ**: [https://github.com/VOICEVOX/voicevox](https://github.com/VOICEVOX/voicevox)
*   **ダウンロード**: 
    *   エディタ版: [VOICEVOX公式サイト](https://voicevox.hiroshiba.jp/)
    *   エンジン版: [VOICEVOX ENGINE Releases](https://github.com/VOICEVOX/voicevox_engine/releases)
*   **起動**: アプリケーション実行前にVOICEVOXを起動してください（デフォルト: `http://127.0.0.1:50021`）。
*   **設定**: `config.json`で接続先URLやスピーカーIDなどを変更可能です。

##### DaVinci Resolve (オプション)
*   **用途**: 動画編集ソフトとの連携（音声・字幕の自動挿入）
*   **公式サイト**: [https://www.blackmagicdesign.com/products/davinciresolve](https://www.blackmagicdesign.com/products/davinciresolve)
*   **要件**: 連携機能を使用する場合、DaVinci Resolveが起動しており、スクリプトAPIが有効であること。

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
