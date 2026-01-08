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

### 実行方法

以下のコマンドでサーバーを起動します。
```powershell
python server.py
```
起動すると `http://0.0.0.0:3000` でPOSTリクエストの待受を開始します。

### 動作確認

サーバー起動中に、別のターミナルからテストスクリプトを実行することで動作を確認できます。
```powershell
python test_voicevox_integration.py
```
Output配下にwavファイルが生成されれば成功です。
