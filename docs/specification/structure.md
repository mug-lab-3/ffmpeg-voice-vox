# ソフトウェア構造 (Software Structure)

本プロジェクトのディレクトリ構成と各レイヤーの役割について記載します。

## 1. ディレクトリ構成

```text
ffmpeg-voice-vox/
├── run.py                 # エントリーポイント (Flaskサーバー起動)
├── config.json            # ユーザー設定ファイル
├── docs/                  # ドキュメント
│   └── specification/     # 詳細仕様書
│       ├── structure.md   # 本ファイル
│       ├── api-server.md  # API・アーキテクチャ仕様
│       ├── system-behavior.md # 動作仕様・挙動
│       └── user-config.md # 設定項目・バリデーション仕様
├── logs/                  # ログ出力先
├── app/                   # アプリケーションパッケージ
│   ├── api/               # APIレイヤー (HTTPハンドラ)
│   ├── services/          # サービスレイヤー (ビジネスロジック)
│   ├── core/              # コアレイヤー (デバイス/外部Client)
│   ├── config.py          # 設定管理ロジック
│   ├── schemas.py         # 設定Pydanticスキーマ
│   └── web/               # WebUI用静的ファイル配信ルート
├── static/                # フロントエンド静的ファイル
└── templates/             # HTMLテンプレート
```

## 2. 関心の分離 (Separation of Concerns)

本システムは以下のレイヤー構造に従い、責務を明確に分けています。

- **Presentation Layer (WebUI)**: HTML/JSによるユーザーインターフェース。
- **Routing Layer (app/api/routes)**: HTTPリクエストの受け口。入力の型検証を担当。
- **Service Layer (app/services)**: 各APIに対応した独立した処理メソッド。
- **Domain Layer (app/services/processor)**: ストリーム処理や音声合成の順序制御。
- **Infrastructure Layer (app/core)**: FFmpegプロセス監視、VoiceVox通信、Resolve連携の実装。

## 3. コンポーネント間の連携フロー

1.  **入力**: `Whisper` 等の外部ソースが `POST /` にストリームを送信。
2.  **解析**: `StreamProcessor` がJSONを切り出し、内容を解析。
3.  **合成**: `VoiceVoxClient` を経由して音声を生成。
4.  **保存**: `AudioManager` がファイル出力とメタデータ作成を実行。
5.  **通知**: `EventManager` (SSE) を通じてWebUIにリアルタイムで反映。
