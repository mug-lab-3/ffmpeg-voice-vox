# セットアップガイド

本アプリケーションを使用するためのセットアップ手順です。PC操作に慣れていない方でも進められるよう、外部ツールの取得から配置、起動後の設定までを丁寧に説明します。

> [!NOTE]
> Windows の場合は自動セットアップスクリプト (`install.bat`) も用意されていますが、本ガイドではエラー時の対応や仕組みを理解するための「手動セットアップ」を中心に解説します。

---

## 1. アプリケーション（本体）の入手

まずは GitHub から本アプリのソースコードをダウンロードします。

1. [GitHub リポジトリ](https://github.com/mug-lab-3/ffmpeg-voice-vox)にアクセスします。
2. 右上の緑色の **[<> Code]** ボタンをクリックします。
3. **[Download ZIP]** を選択します。
   ![GitHub からのダウンロード手順プレースホルダー](images/setup/github_download.png)
4. ダウンロードした ZIP ファイルを、デスクトップなど任意の場所に展開（解凍）します。
   > [!IMPORTANT]
   > 展開したフォルダ名は `ffmpeg-voice-vox-main` となっている場合があります。必要に応じて分かりやすい名前に変更してください。

---

## 2. 実行環境 (uv) の準備

本アプリは Python の高速な環境管理ツール **[uv](https://docs.astral.sh/uv/)** を使用して動作します。これにより、ライブラリのインストールでトラブルが起きにくくなります。

### Windows の場合
1. スタートメニューを右クリックして「ターミナル」（または PowerShell）を開きます。
2. 以下のコマンドをコピーして貼り付け、実行します。
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. インストール完了後、一度ターミナルを閉じて開き直すことで `uv` コマンドが使えるようになります。
![uv のインストールプレースホルダー](images/setup/uv_install_win.png)

### Mac の場合
1. ターミナルを開き、以下のコマンドを実行します。
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. あるいは、Homebrew を使用している場合は `brew install uv` でもインストール可能です。

---

## 3. 外部ツールの取得と配置

アプリを動かすために必要なツールをダウンロードし、アプリのフォルダ内の `tools` や `models` に配置します。

### フォルダ構成のイメージ
以下のような構成を目指してファイルを配置していきます。
```text
ffmpeg-voice-vox/（アプリのルート）
├── tools/
│   └── ffmpeg/（展開した FFmpeg）
├── models/
│   ├── ggml-large-v3-turbo.bin（Whisper モデル）
│   └── ggml-silero-v6.2.0.bin（VAD モデル）
├── voicevox_controller.py
└── ...
```

> [!NOTE]
> VOICEVOX は通常のインストール手順（インストーラー版）で PC にインストールされていれば OK です。特定のフォルダに配置する必要はありません。

### ① FFmpeg (Whisper 対応版)
通常の FFmpeg ではなく、音声認識機能 (Whisper) が内蔵されたものが必要です。

- **Windows**: [Gyan.dev (配布ページ)](https://www.gyan.dev/ffmpeg/builds/) から [ffmpeg-git-full.7z (直接ダウンロード)](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z) を入手・展開し、中身を `tools/ffmpeg/` に配置します。
- **Mac**: [Evermeet.cx](https://evermeet.cx/ffmpeg/) 等から最新のビルドを入手するか、Whisper フィルターが有効なビルドを準備してください。
![FFmpeg の配置プレースホルダー](images/setup/ffmpeg_install.png)

### ② VOICEVOX
音声合成エンジンです。エディタ版（通常版）を用意します。

- [VOICEVOX 公式サイト](https://voicevox.hiroshiba.jp/) からダウンロードします。
- > [!TIP]
  > **どのバージョンを選べばいい？**
  > - **対応OS**: お使いの PC に合わせて選択してください。
  > - **モード**: 
  >   - **GPU (DirectML / NVIDIA) [推奨]**: 高性能なグラフィックボード（GPU）を利用して高速に音声を生成します。GPU がない場合でも自動的に CPU で動作するため、**基本的にはこちらを選べば OK** です。
  >   - **CPU**: ダウンロードサイズが小さく非常に軽量です。古い PC や、ディスク容量を極限まで節約したい場合のみ選択してください。
  > - **パッケージ形式**: 
  >   - **インストーラー版 [推奨]**: 公式で推奨されている形式です。PC にインストールして起動しておくだけで本アプリと自動的に連携します。
  >   - **ZIP版**: アプリをインストールしたくない場合や、特定のフォルダでポータブルに管理したい場合に使用します。

### ③ 学習済みモデル (Whisper / VAD)
音声認識の「脳」となるファイルです。

- **Whisper モデル**: [ggerganov/whisper.cpp (公式リポジトリ)](https://huggingface.co/ggerganov/whisper.cpp/tree/main) から [ggml-large-v3-turbo.bin (直接ダウンロード)](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin) を入手します。
  - > [!TIP]
    > **PC スペックに応じたモデルの選び方**
    > - `ggml-large-v3-turbo.bin` (**推奨**): 速度と精度のバランスが良く、多くの方に最適です。
    > - `ggml-large-v3.bin`: 最も高精度ですが、動作が重くなります。（VRAM 10GB以上推奨）
    > - `ggml-small.bin`: 動作が非常に軽く、古いPCやCPUのみで動かす場合に適しています。
    >
    > 他のモデルは [ggerganov/whisper.cpp (Hugging Face)](https://huggingface.co/ggerganov/whisper.cpp/tree/main) から入手可能です。
- **VAD モデル**: [ggml-org/whisper-vad (公式リポジトリ)](https://huggingface.co/ggml-org/whisper-vad) から [ggml-silero-v6.2.0.bin (直接ダウンロード)](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin) を入手します。
- これら 2 つのファイルを `models/` フォルダに配置します。

---

## 4. アプリの起動準備

本アプリでは `uv` が必要なライブラリを自動で管理するため、個別に `pip install` する必要はありません。

### 起動ファイルの用意 (Windows)
毎回コマンドを打つのは大変なので、起動用のバッチファイルを作成します。アプリのフォルダに `run.bat` という名前のファイルを作成し、以下の内容を貼り付けて保存してください。

```batch
@echo off
chcp 65001 >nul
uv run voicevox_controller.py
pause
```

---

## 5. アプリの起動と初期設定

### 起動
1. **VOICEVOX** を先に起動しておきます。
2. **Windows**: 作成した `run.bat` をダブルクリックします。
3. **Mac**: ターミナルでアプリのフォルダに移動し、`uv run voicevox_controller.py` を実行します。
4. 初回起動時は必要なライブラリの自動ダウンロードが行われるため、少し時間がかかります。完了するとブラウザが自動的に開き、Web UI が表示されます。

### WebUI での設定
ブラウザに表示された画面で、先ほど配置したツールのパスを指定します。

1. **FFmpeg Configuration**: `FFmpeg Path` を指定します。
   - **Windows**: `tools/ffmpeg/bin/ffmpeg.exe`
   - **Mac**: `tools/ffmpeg/ffmpeg` (配置したバイナリの場所)
2. **Models Configuration**: 
   - `Whisper Model Path` に `models/ggml-large-v3-turbo.bin` を指定します。
   - `VAD Model Path` に `models/ggml-silero-v6.2.0.bin` を指定します。
3. **System Settings**: `Output Directory` に、生成された音声ファイルを保存したいフォルダを指定します。
![WebUI での設定画面プレースホルダー](images/setup/webui_config.png)

---

## 6. 動作確認

設定が完了すると、画面上部の **[VOICEVOX CONNECTED]** などのインジケータが点灯します。

1. 画面右上の **[START]** ボタンを押します。
2. マイクに向かって話すと、画面に文字起こし結果が表示され、VOICEVOX から音声が再生されれば成功です！

![動作確認プレースホルダー](images/setup/success.png)
