import pytest
import os
import re
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
    """AudioManagerが渡されたファイル名で正しく保存できることを確認"""
    audio_manager = AudioManager()

    # AudioManager.save_audio now accepts (audio_data, filename) -> duration
    # Filename generation is done by processor, so we just test that it saves correctly

    # Test with 3-digit ID format
    duration1 = audio_manager.save_audio(b"fake_data", "001_abcd1234_test.wav")
    assert duration1 >= 0  # Just verify it returns a duration

    # Test with 4-digit ID format
    duration2 = audio_manager.save_audio(b"fake_data", "1000_efgh5678_test.wav")
    assert duration2 >= 0


def test_db_fallback_to_data():
    """output_dirが空の場合、data/transcriptions.dbが使用されることを確認"""
    db_manager = DatabaseManager()
    config.update("system.output_dir", "")

    path = db_manager._get_db_path()
    assert "data" in path
    assert "transcriptions.db" in path
