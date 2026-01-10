# FFmpeg Voicevox Integration

本プロジェクトは、FFmpeg + Whisperなどからの音声認識結果(JSON)を受け取り、
Voicevoxを使用して合成音声を生成・保存するサーバーアプリケーションです。

## 開発環境構築 (Developer Guide)

### 必須要件
* **OS**: Windows (※`winsound`モジュールを使用しているため)
* **Python**: 3.x
* **VOICEVOX**: 音声合成エンジンとして必要

### セットアップ手順

1. **Pythonの確認**
   Pythonがインストールされていることを確認してください。
   ```powershell
   python --version
   ```

2. **依存ライブラリのインストール**
   プロジェクトフォルダ内で以下のコマンドを実行し、Flask等をインストールします。
   ```powershell
   pip install -r requirements.txt
   ```

3. **VOICEVOXの起動**
   VOICEVOXエディタまたはエンジンを起動してください。
   本アプリはデフォルトで `http://127.0.0.1:50021` にアクセスします。
   (設定ファイル `config.json` で変更可能)

### 実行方法

以下のコマンドでサーバーを起動します。
```powershell
python run.py
```
起動するとブラウザが自動的に開き、Web UIが表示されます。
また、初回起動時に `config.json` が生成されます。

### 構成
Refactored (v2) 構成になっています。
* `run.py`: エントリーポイント
* `app/`: アプリケーションコード
* `config.json`: 設定ファイル
* `logs/`: ログファイル

詳細は `doc/` フォルダ内のドキュメントを参照してください。
