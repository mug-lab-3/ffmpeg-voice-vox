# API Server Specification

本ソフトウェアのサーバーサイドアーキテクチャおよびAPI仕様について記載します。

## アーキテクチャ概要

本サーバーは、関心の分離（Separation of Concerns）を重視したドメイン駆動な構造を採用しています。
各APIは「薄いルートハンドラ」と「専用のサービスメソッド」の組み合わせで構成されており、高い凝集度と低結合性を実現しています。

### ディレクトリ構造

- **`app/api/`**: APIレイヤー。HTTPプロトコルに関連する処理を担当。
  - **`routes/`**: FlaskのBlueprintを使用したルーティング定義。
  - **`schemas/`**: Pydanticを使用したリクエスト/レスポンスの型定義。
- **`app/services/`**: サービスレイヤー。ビジネスロジックの実体（ハンドラメソッド）を定義。
- **`app/core/`**: コアレイヤー。FFmpeg、VoiceVox、DaVinci Resolve等の外部クライアントやユーティリティ。

## 共通レスポンス形式

すべてのAPIレスポンスは以下の `BaseResponse` を定義しており、一貫した形式で返却します。

```json
{
  "status": "ok",
  "error_code": null,
  "message": null
}
```

- `status`: `"ok"` または `"error"`
- `error_code`: エラーの種類を示す定数文字列（任意）
  - 例: `"INVALID_ARGUMENT"` (Pydanticバリデーションエラー時)
- `message`: ユーザー向けのエラーメッセージ（任意）
- **バリデーションエラー時の追加データ**:
  - `422 Unprocessable Entity` 返却時には、UI側の状態を即座に復元できるよう、**現在の最新かつ有効な設定内容**（後述の `ConfigResponse` と同等のデータ）が同封されます。

### 主なHTTPステータスコード
- **200 OK**: リクエスト成功
- **400 Bad Request**: リクエストの構文エラー
- **422 Unprocessable Entity**: バリデーションエラー（値の範囲外など）
- **500 Internal Server Error**: サーバー内部エラー

## APIエンドポイント詳細

各設定（Config）はカテゴリごとに独立したエンドポイントを持ちます。

### 1. Config (設定関連)

#### `GET /api/config`
現在設定されている合成パラメータやディレクトリ情報を取得します。

- **レスポンス**: `ConfigResponse` (status, config, outputDir, etc.)

#### `POST /api/config/synthesis` (音声パラメータ更新)
- **ボディ**: `{"speaker_id": int, "speed_scale": float, ...}`
- **制約**: `speed_scale` (0.5-1.5), `pitch_scale` (-0.15-0.15), `intonation_scale` (0-2.0), `volume_scale` (0-2.0)

#### `POST /api/config/resolve` (Resolve設定更新)
- **ボディ**: `{"enabled": bool, "audio_track_index": int, ...}`

#### `POST /api/config/system` (システム設定等)
- **ボディ**: `{"output_dir": string}`

#### `POST /api/config/ffmpeg` (FFmpeg詳細設定)
- **ボディ**: `{"ffmpeg_path": string, "queue_length": int, ...}`

(※ 従来の `POST /api/config` への一括送信も後方互換性のために維持されていますが、上記ドメイン別APIの使用が推奨されます)

---

### 2. Control (制御・操作関連)

#### `GET /api/control/state`
システム全体の稼働状態を取得します。

- **レスポンス**: `ControlStateResponse` (enabled, playback, connection statuses)

#### `POST /api/control/state`
自動合成機能の有効/無効を切り替えます。
- **ボディ**: `{"enabled": boolean}`

#### `POST /api/control/resolve_insert`
生成済みの音声ファイルをDaVinci Resolveのタイムラインへ挿入します。
- **ボディ**: `{"filename": string}`

#### `POST /api/control/play`
生成済みの音声ファイルを再生します。
- **ボディ**: `{"filename": string, "request_id": string (optional)}`
- **挙動**:
    - リクエストはサーバー側でキューイングされ、受信順に処理されます。
    - 既に再生中の場合は、現在の再生が終了するのを待機してから次の再生を開始します。
    - `request_id` が指定された場合、そのIDは再生状態管理に使用され、クライアント側での同期に役立ちます。

---

### 3. その他
- `GET /api/speakers`: 話者一覧取得
- `GET /api/logs`: 処理履歴取得
- `GET /api/stream`: SSE (リアルタイム通知)
