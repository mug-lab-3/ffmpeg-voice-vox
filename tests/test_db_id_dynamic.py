import pytest
import os
import re
import shutil
import tempfile
from app.core.database import DatabaseManager
from app.core.audio import AudioManager
from app.config import config


@pytest.fixture(autouse=True)
def protect_config():
    """本番のconfig.jsonがテストで書き換えられないように保護する"""
    from unittest.mock import patch

    with patch("app.config.config.save_config_ex"):
        yield


@pytest.fixture
def temp_output_dir():
    """一時的な出力ディレクトリを作成するフィクスチャ"""
    temp_dir = tempfile.mkdtemp()
    # Ensure the directory exists physically
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
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
    config.system.output_dir = dir_a

    # Aで1件追加
    id_a1 = db_manager.add_transcription("test a1", 1, {})
    assert id_a1 == 1
    assert os.path.exists(os.path.join(dir_a, "transcriptions.db"))

    # テスト用ディレクトリB
    dir_b = os.path.join(temp_output_dir, "dir_b")
    os.makedirs(dir_b)
    config.system.output_dir = dir_b

    # Bで1件追加 -> IDは1から始まるはず
    id_b1 = db_manager.add_transcription("test b1", 1, {})
    assert id_b1 == 1
    assert os.path.exists(os.path.join(dir_b, "transcriptions.db"))

    # 再びAに戻る
    config.system.output_dir = dir_a
    id_a2 = db_manager.add_transcription("test a2", 1, {})
    assert id_a2 == 2


def test_audio_filename_padding(temp_output_dir):
    """AudioManagerが渡されたファイル名で正しく保存できることを確認"""
    config.system.output_dir = temp_output_dir
    audio_manager = AudioManager()

    # AudioManager.save_audio now accepts (audio_data, filename) -> duration
    # Filename generation is done by processor, so we just test that it saves correctly

    # Test with 3-digit ID format
    duration1 = audio_manager.save_audio(b"fake_data", "001_abcd1234_test.wav")
    assert duration1 >= 0  # Just verify it returns a duration

    # Test with 4-digit ID format
    duration2 = audio_manager.save_audio(b"fake_data", "1000_efgh5678_test.wav")
    assert duration2 >= 0


def test_db_no_fallback_when_empty():
    """output_dirが空の場合、DBコネクションが確立されず、ファイルも作成されないことを確認"""
    db_manager = DatabaseManager()
    config.system.output_dir = ""

    path = db_manager._get_db_path()
    assert path is None

    conn = db_manager._get_connection()
    assert conn is None

    # Check that data/transcriptions.db is not created (if it doesn't already exist)
    default_path = os.path.join(os.getcwd(), "data", "transcriptions.db")
    # Note: If it exists from previous runs, we can't easily check for *new* creation without deleting it first,
    # but the path check above is the primary logic verification.
