---
trigger: always_on
---

# 基本ルール

- When generating the Plan, Task, and Walkthrough, please ensure all descriptions are written in Japanese for better clarity.

## 回答方針

* プロンプトへの情報の提示・回答はすべて日本語で行う
* 作業計画書も日本語で作成する
* 文字コードは常にUTF-8とする


## 目的

本アプリは、FFmpegとWhisperを用いた音声認識結果を活用し、
VoiceVoxによる合成音声生成と、DaVinci Resolveへの自動取り込み
（字幕テキストおよび音声ファイルのタイムライン挿入）を行うことを目的としています。

ユーザーの手を煩わせることなく、音声・字幕素材の生成から動画編集ソフトへの配置までを
シームレスに連携させることを目指します。

## 対応プラットフォーム

* **Windows / Mac 両対応**
  * 現在のコードベースが特定のOS（Windowsなど）に依存している場合でも、最終的には両OSで動作することを要件とします。
  * 新規実装や改修を行う際は、クロスプラットフォーム互換性を常に考慮してください。

## 技術スタック・構成

* **言語**: Python 3.x
* **フレームワーク**: Flask (Web UI / API)
* **音声合成**: VoiceVox
* **連携対象**: DaVinci Resolve (Scripting API)
* **構成**:
  * `run.py`: アプリケーションエントリーポイント
  * `app/`: 主要なロジック（`core`, `services`, `web` など）
  * `config.json`: ユーザー設定