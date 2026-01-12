# API Server Specification

本ソフトウェアのサーバーサイドアーキテクチャおよびAPI仕様について記載します。

## アーキテクチャ概要

本サーバーは、関心の分離（Separation of Concerns）を重視したドメイン駆動な構造を採用しています。
各APIは「薄いルートハンドラ」と「専用のサービスメソッド」の組み合わせで構成されています。

### ディレクトリ構造

- **`app/api/`**: APIレイヤー。HTTPプロトコルに関連する処理を担当。
  - **`routes/`**: FlaskのBlueprintを使用したルーティング定義。
  - **`schemas/`**: Pydanticを使用したリクエスト/レスポンスの型定義。
- **`app/services/`**: サービスレイヤー。ビジネスロジックの実体。
- **`app/core/`**: コアレイヤー。FFmpeg、VoiceVox、DaVinci Resolve等の外部クライアント。

## 共通レスポンス形式

すべてのAPIレスポンスは以下の `BaseResponse` 形式を採用しています。

```json
{
  "status": "ok",
  "error_code": null,
  "message": null
}
```

- `status`: `"ok"` または `"error"`
- `error_code`: エラーの種類を示す定数文字列（任意）
- `message`: ユーザー向けのエラーメッセージ（任意）

## APIエンドポイント詳細

### 1. Config (設定関連)

#### `GET /api/config`
現在設定されている構成情報を取得。

#### `POST /api/config/synthesis` (音声パラメータ更新)
- **ボディ**: `{"speaker_id": int, "speed_scale": float, ...}`
- **制約**: `speed_scale` (0.5-1.5), `pitch_scale` (-0.15-0.15), etc.

#### `POST /api/config/resolve` (Resolve設定更新)
- **ボディ**: `{"enabled": bool, "audio_track_index": int, "video_track_index": int, ...}`

#### `POST /api/config/system`
- **ボディ**: `{"output_dir": string}`

#### `POST /api/config/ffmpeg`
- **ボディ**: `{"ffmpeg_path": string, "queue_length": int, ...}`

---

### 2. Control (制御・操作関連)

#### `GET /api/control/state`
システム全体の稼働状態を取得。

#### `POST /api/control/state`
自動合成機能の有効/無効を切り替え。
- **ボディ**: `{"enabled": boolean}`

#### `POST /api/control/resolve_insert`
生成済みの音声ファイルをResolveタイムラインへ挿入。
- **ボディ**: `{"id": integer}`

#### `POST /api/control/play`
生成済みの音声ファイルを再生。
- **ボディ**: `{"id": integer}`

#### `POST /api/control/delete`
ログエントリと関連ファイルを削除。
- **ボディ**: `{"id": integer}`

#### `POST /api/control/update_text`
既存のログエントリのテキスト内容を更新。
- **ボディ**: `{"id": integer, "text": string}`
- **挙動**: 音声ファイルが存在する場合は物理削除され、ステータスは「pending」に戻ります。

#### `POST /api/control/synthesize`
特定のログエントリをオンデマンドで音声合成。
- **ボディ**: `{"id": integer}`

---

### 3. その他

- `GET /api/speakers`: 話者一覧取得
- `GET /api/logs`: 処理履歴取得
- `GET /api/stream`: SSE (リアルタイム通知)
- `GET /api/resolve/clips`: Resolve内のText+クリップ一覧
- `GET /api/resolve/bins`: Resolve内のビン一覧
