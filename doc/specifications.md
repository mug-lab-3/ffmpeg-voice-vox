# 仕様書 (Specifications)

## 1. 動作環境・要件
*   **OS**: Windows (推奨)
*   **Runtime**: Python 3.x
*   **依存サービス**:
    *   **Voicevox**: ローカルホスト (`127.0.0.1`) のポート `50021` で稼働している必要があります。
*   **サーバー設定**:
    *   **Host**: `127.0.0.1`
    *   **Port**: `3000`

## 2. インターフェース仕様

### 2.1 入力インターフェース (受信)
Whisperサーバー等の外部ソースからのストリーム入力を受け付けます。

*   **Endpoint**: `POST /`
*   **Method**: Stream Processing
*   **Input Format (JSON)**:
    受信データは以下のJSONオブジェクトが連続したストリームであることを期待します。
    ```json
    {
      "text": "認識されたテキスト",
      "start": 1000,   // 開始時間 (ミリ秒)
      "end": 2500      // 終了時間 (ミリ秒)
    }
    ```

### 2.2 フロントエンド API
Web UIとの通信に使用するREST APIです。

*   **設定管理 (`/api/config`)**
    *   `GET`: 現在のVoicevox設定を取得。
    *   `POST`: 設定を更新。
    *   **パラメータ**:
        *   `speaker`: 話者ID (int)
        *   `speedScale`, `pitchScale`, `intonationScale`, `volumeScale`: 各種パラメータ (float)

*   **ログ取得 (`/api/logs`)**
    *   `GET`: 最近の処理ログ（最大50件）を取得。
    *   **Response**:
        ```json
        [
          {
            "timestamp": "HH:MM:SS",
            "text": "...",
            "duration": "1.23s",
            "filename": "...",
            "config": { ... }
          },
          ...
        ]
        ```

*   **制御系 API (`/api/control/*`)**
    *   `/api/control/state` (GET/POST): 自動合成機能のON/OFF切り替え。
    *   `/api/control/play` (POST): 指定されたファイル名の音声ファイルを再生（サーバー側で再生）。
    *   `/api/control/delete` (POST): 指定された音声ファイルとSRTファイルを削除。

## 3. 出力ファイル仕様
音声合成が成功すると `output/` フォルダに以下のファイルが生成されます。

### 3.1 ファイル命名規則
`{開始時間(ms)}_{話者名}_{テキスト先頭8文字}.{拡張子}`
*   例: `001500_ずんだもん_こんにちは.wav`

### 3.2 生成ファイル
1.  **WAVファイル**: Voicevoxによって生成された音声データ。
2.  **SRTファイル**: 字幕データ。
    *   開始時刻: `00:00:00,000` 固定
    *   終了時刻: 音声の長さに合わせて自動設定

## 4. 自動シャットダウン
*   サーバーは最後のアクティビティから **5分間 (300秒)** アクセスがない場合、自動的に終了します。
