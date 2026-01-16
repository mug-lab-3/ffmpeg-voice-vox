import pytest
import os
import re
from unittest.mock import MagicMock, patch
from app.services.processor import StreamProcessor


@pytest.fixture
def mock_dependencies():
    client = MagicMock()
    audio_manager = MagicMock()
    return client, audio_manager


def test_filename_generation_format(mock_dependencies):
    """Verify _generate_filename produces ID_HASH_PREFIX.wav format."""
    client, audio_manager = mock_dependencies
    mock_syn_config = MagicMock()
    processor = StreamProcessor(client, audio_manager, mock_syn_config)

    text = "こんにちは世界"
    db_id = 123
    config = {"speaker_id": 1, "speed_scale": 1.0, "pitch_scale": 0.0}

    filename = processor._generate_filename(db_id, text, config)

    # regex: ^123_[8-char-hex]_.+\.wav$
    pattern = r"^123_[a-f0-9]{8}_.+\.wav$"
    assert re.match(
        pattern, filename
    ), f"Filename '{filename}' does not match expected pattern"


def test_hash_consistency(mock_dependencies):
    """Verify same inputs produce same hash in filename."""
    client, audio_manager = mock_dependencies
    mock_syn_config = MagicMock()
    processor = StreamProcessor(client, audio_manager, mock_syn_config)

    text = "TestingConsistency"
    db_id = 1
    config = {"speaker_id": 1, "speed_scale": 1.0}

    name1 = processor._generate_filename(db_id, text, config)
    name2 = processor._generate_filename(db_id, text, config)

    assert name1 == name2


def test_hash_sensitivity_text(mock_dependencies):
    """Verify different text produces different hash."""
    client, audio_manager = mock_dependencies
    mock_syn_config = MagicMock()
    processor = StreamProcessor(client, audio_manager, mock_syn_config)

    db_id = 1
    config = {"speaker_id": 1}

    name1 = processor._generate_filename(db_id, "Text A", config)
    name2 = processor._generate_filename(db_id, "Text B", config)

    # Confirm hash part differs
    hash1 = name1.split("_")[1]
    hash2 = name2.split("_")[1]

    assert hash1 != hash2


def test_hash_sensitivity_config(mock_dependencies):
    """Verify different config produces different hash."""
    client, audio_manager = mock_dependencies
    mock_syn_config = MagicMock()
    processor = StreamProcessor(client, audio_manager, mock_syn_config)

    text = "SameText"
    db_id = 1

    config1 = {"speaker_id": 1, "speed_scale": 1.0}
    config2 = {"speaker_id": 1, "speed_scale": 1.1}

    name1 = processor._generate_filename(db_id, text, config1)
    name2 = processor._generate_filename(db_id, text, config2)

    hash1 = name1.split("_")[1]
    hash2 = name2.split("_")[1]

    assert hash1 != hash2


def test_hash_ignores_irrelevant_config(mock_dependencies):
    """Verify irrelevant config keys don't change hash."""
    client, audio_manager = mock_dependencies
    mock_syn_config = MagicMock()
    processor = StreamProcessor(client, audio_manager, mock_syn_config)

    text = "SameText"
    db_id = 1

    config1 = {"speaker_id": 1, "speed_scale": 1.0, "ui_color": "blue"}
    config2 = {"speaker_id": 1, "speed_scale": 1.0, "ui_color": "red"}

    name1 = processor._generate_filename(db_id, text, config1)
    name2 = processor._generate_filename(db_id, text, config2)

    assert name1 == name2
