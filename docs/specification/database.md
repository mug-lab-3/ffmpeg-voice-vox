# Database Specification

本プロジェクトで使用する SQLite データベースのスキーマおよび永続化されるデータについて定義します。
データベースファイル（`transcriptions.db`）は、設定されている出力ディレクトリ（`output_dir`）の直下に作成されます。

## テーブル定義

### `transcriptions` テーブル

音声合成のリクエストおよび生成結果の履歴を保持します。

| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| `id` | INTEGER | プライマリキー、連番 |
| `timestamp` | DATETIME | レコード作成日時（UTC） |
| `text` | TEXT | 音声合成されたテキスト内容 |
| `speaker_id` | INTEGER | VOICEVOXのスタイルID |
| `speaker_name` | TEXT | 合成時のキャラクター名（例: ずんだもん） |
| `speaker_style` | TEXT | 合成時のスタイル名（例: あまあま） |
| `speed_scale` | REAL | 話速（0.5 〜 1.5） |
| `pitch_scale` | REAL | 音高（-0.15 〜 0.15） |
| `intonation_scale` | REAL | 抑揚（0.0 〜 2.0） |
| `volume_scale` | REAL | 音量（0.0 〜 2.0） |
| `pre_phoneme_length` | REAL | 開始無音時間（0.0 〜 1.5） |
| `post_phoneme_length` | REAL | 終了無音時間（0.0 〜 1.5） |
| `output_path` | TEXT | 生成された音声ファイルの相対パス（未生成時は NULL） |
| `audio_duration` | REAL | 音声の長さ（秒、デフォルト 0.0） |

## 永続化とマイグレーション

- **永続化の目的**: キャラクター名とスタイル名を文字列で保持することで、VOICEVOXが停止している状態での起動や、将来のVOICEVOXアップデートによりIDの定義が変更された場合でも、当時の情報を正確に表示できるようにします。
- **自動マイグレーション**: アプリケーション起動時に `DatabaseManager` が既存の DB 構造をチェックし、不足しているカラム（`speaker_name`, `speaker_style`）があれば自動的に `ALTER TABLE` を実行して拡張します。
