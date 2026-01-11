import pytest
import os
import shutil
import tempfile
from app.core.database import DatabaseManager
from app.core.audio import AudioManager
from app.config import config


@pytest.fixture
def temp_output_dir():
    """一時的な出力ディレクトリを作成するフィクスチャ"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # SQLiteがファイルを掴んでいる可能性があるため、Windowsではエラーを無視するか
    # 接続を確実に閉じる必要があります。ここでは簡易的にエラーを無視します。
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dynamic_db_switching(temp_output_dir):
    """output_dirを変更した際に、異なるDBファイルが作成され、IDがリセットされることを確認"""
    db_manager = DatabaseManager()

    # テスト用ディレクトリA
    dir_a = os.path.join(temp_output_dir, "dir_a")
    os.makedirs(dir_a)
    config.update("system.output_dir", dir_a)

    # Aで1件追加
    id_a1 = db_manager.add_transcription("test a1", 1, {})
    assert id_a1 == 1
    assert os.path.exists(os.path.join(dir_a, "transcriptions.db"))

    # テスト用ディレクトリB
    dir_b = os.path.join(temp_output_dir, "dir_b")
    os.makedirs(dir_b)
    config.update("system.output_dir", dir_b)

    # Bで1件追加 -> IDは1から始まるはず
    id_b1 = db_manager.add_transcription("test b1", 1, {})
    assert id_b1 == 1
    assert os.path.exists(os.path.join(dir_b, "transcriptions.db"))

    # 再びAに戻る
    config.update("system.output_dir", dir_a)
    id_a2 = db_manager.add_transcription("test a2", 1, {})
    assert id_a2 == 2


def test_audio_filename_padding():
    """音声ファイル名が3桁0埋め（1000以上の場合はそのまま）であることを確認"""
    audio_manager = AudioManager()

    # 正常ケース (3桁)
    name1, _ = audio_manager.save_audio(b"fake_data", "test", 1)
    assert name1.startswith("001_") or name1.startswith("001_")  # check prefix
    assert name1 == "001_test.wav"

    # 1000以上のケース
    name1000, _ = audio_manager.save_audio(b"fake_data", "test", 1000)
    assert name1000.startswith("1000_")
    assert name1000 == "1000_test.wav"


def test_db_fallback_to_data():
    """output_dirが空の場合、data/transcriptions.dbが使用されることを確認"""
    db_manager = DatabaseManager()
    config.update("system.output_dir", "")

    path = db_manager._get_db_path()
    assert "data" in path
    assert "transcriptions.db" in path
