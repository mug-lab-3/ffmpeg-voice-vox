# 制御内容 (Control Logic)

本システムの内部制御ロジック、特にストリーム処理と音声合成フローについて解説します。

## 1. メイン処理フロー (受信〜合成)

`app/core/processor.py` の `StreamProcessor.process_stream` がストリーム処理の中心となります。

1.  **ストリーム受信**:
    *   `POST /` (定義: `app/web/routes.py`) に対してデータが送られてくると、`StreamProcessor` にストリームが渡されます。
    *   デリミタ（`}`）を検出するたびに、そこまでを1つのJSONオブジェクトとして切り出します。

2.  **JSON解析 (Parsing)**:
    *   `_process_json_chunk` メソッドでパースします。
    *   必須キー (`text`, `start`, `end`) の存在確認を行います。

3.  **合成判定 (Switching)**:
    *   設定マネージャー (`app.config.ConfigManager`) の `system.is_synthesis_enabled` 値を確認します。
    *   **ONの場合**: Voicevox連携処理に進みます。
    *   **OFFの場合**: ログにスキップ情報を出力し、処理を中断します。

4.  **Voicevox連携＆保存**:
    *   **Audio Query**: `VoiceVoxClient.audio_query` を呼び出し、パラメータを取得します。
    *   **Synthesis**: `VoiceVoxClient.synthesis` で音声データを生成します。設定値（speed, pitch等）は `config.json` からロードされた値を適用します。
    *   **保存**: `AudioManager.save_audio` が `output/` フォルダへの保存とSRT生成を担当します。

5.  **ログ更新**:
    *   処理結果はメモリ上のリスト(`received_logs`)に追加されると同時に、Python標準の `logging` モジュールを通じて `logs/app.log` にも記録されます。

## 2. 状態管理 (State Management)

### 2.1 設定とステート
*   設定値は `app/config.py` の `ConfigManager` クラスで一元管理されます。
*   ファイル(`config.json`)と同期しており、アプリケーション内で共有されるシングルトンインスタンスとして機能します。

### 2.2 再生管理 (Playback)
*   **モジュール**: `app/core/audio.py` の `AudioManager` クラスが担当。
*   **排他制御**: `playback_lock` を使用してスレッドセーフに再生状態を管理します。
*   **非同期実行**: `winsound` による再生は別スレッドで行われ、Web APIの応答をブロックしません。

## 3. 自動監視 (Watchdog)
*   **エントリーポイント**: `run.py` 内で監視スレッドが起動します。
*   **仕組み**: `last_activity_time` を監視し、**300秒(5分)** 無操作状態が続くとプロセスを終了します。

## 4. エラーハンドリング
*   **モジュール間の分離**: `StreamProcessor` 内で例外をキャッチし、一部のデータ不良がサーバー全体の停止につながらないように設計されています。
*   **ログ**: 予期しないエラーは `logs/app.log` にスタックトレースと共に記録されます。
