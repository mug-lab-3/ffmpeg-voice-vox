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

すべてのAPIレスポンスは以下の `BaseResponse` を継承しており、ステータスを一貫した形式で返却します。

```json
{
  "status": "ok",
  "message": null
}
```

- `status`: `"ok"` または `"error"`
- `message`: エラー時の詳細メッセージ（任意）

## APIエンドポイント詳細

### 1. Config (設定関連)

#### `GET /api/config`
現在設定されている合成パラメータやディレクトリ情報を取得します。

- **レスポンスパラメータ**:
| 項目 | 型 | 説明 |
| :--- | :--- | :--- |
| `config` | object | 合成設定（speaker_id, speed_scale, resolve設定等を含む） |
| `outputDir` | string | 音声ファイルの出力先ディレクトリ |
| `resolve_available` | boolean | DaVinci Resolveと通信可能か |
| `voicevox_available` | boolean | VoiceVoxエンジンと通信可能か |

#### `POST /api/config`
各設定値を更新します。

- **リクエストボディ (JSON)**:
| 項目 | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `speaker` | integer | × | 話者ID |
| `speedScale` | float | × | 話速 (0.5 〜 1.5) |
| `pitchScale` | float | × | 音高 (-0.15 〜 0.15) |
| `intonationScale` | float | × | 抑揚 (0.0 〜 2.0) |
| `volumeScale` | float | × | 音量 (0.0 〜 2.0) |
| `outputDir` | string | × | 出力先ディレクトリパス |
| `templateBin` | string | × | Resolveのテンプレートビン名 |
| `templateName` | string | × | Resolveのテンプレート名 |
| `ffmpeg` | object | × | FFmpegの詳細設定 (dict形式) |

---

### 2. Control (制御・操作関連)

#### `GET /api/control/state`
システム全体の稼働状態を取得します。

- **レスポンスパラメータ**:
| 項目 | 型 | 説明 |
| :--- | :--- | :--- |
| `enabled` | boolean | 自動合成が有効化されているか |
| `playback` | object | 現在の再生状態（再生中のファイル名、長さ等） |
| `resolve_available` | boolean | DaVinci Resolveの接続状態 |
| `voicevox_available` | boolean | VoiceVoxの接続状態 |

#### `POST /api/control/state`
自動合成機能の有効/無効を切り替えます。

- **リクエストボディ (JSON)**:
| 項目 | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `enabled` | boolean | ◯ | `true` で開始、`false` で停止 |

#### `POST /api/control/resolve_insert`
生成済みの音声ファイルをDaVinci Resolveのタイムラインへ挿入します。

- **リクエストボディ (JSON)**:
| 項目 | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `filename` | string | ◯ | 挿入するファイル名（拡張子含む） |

#### `POST /api/control/play` / `POST /api/control/delete`
音声の再生または削除を行います。

- **リクエストボディ (JSON)**:
| 項目 | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `filename` | string | ◯ | 対象のファイル名 |

---

### 3. System (システム・共通機能)

#### `GET /api/ffmpeg/devices`
サーバー側で認識されている録音デバイスの一覧を取得します。

- **レスポンス**: `{"devices": ["Device A", "Device B"], "status": "ok"}`

#### `POST /api/system/browse` / `browse_file`
サーバー側でフォルダ/ファイル選択ダイアログを開き、選択されたパスを返します。

- **レスポンス**: `{"path": "C:\\Selected\\Path", "status": "ok"}`

---

### 4. Legacy/Stream (基底機能)

#### `GET /api/logs`
過去の処理履歴を取得します。

- **レスポンス**: `{"logs": [{ "timestamp": "...", "text": "...", "filename": "..." }], "status": "ok"}`

#### `POST /` (Whisper入力)
外部プロセスからの文字起こしデータを受信します。

- **リクエストボディ (JSON Streaming)**:
| 項目 | 型 | 説明 |
| :--- | :--- | :--- |
| `text` | string | 認識されたテキスト |
| `start` | integer | 開始時間 (ミリ秒) |
| `end` | integer | 終了時間 (ミリ秒) |

## データバリデーション

APIへの入力は [Pydantic](https://docs.pydantic.dev/) モデルによって厳密に検証されます。
不正なデータ形式が送信された場合、ルーティング層で自動的にエラー（400 Bad Request）として処理され、ビジネスロジックの安全性が保たれます。
