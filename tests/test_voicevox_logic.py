import pytest
from unittest.mock import patch, MagicMock
import json
from app.core.voicevox import VoiceVoxClient


@pytest.fixture
def vv_client():
    return VoiceVoxClient()


@patch("urllib.request.urlopen")
@patch("urllib.request.Request")
def test_get_speakers_success(mock_request, mock_urlopen, vv_client):
    # Mock API response
    mock_res = MagicMock()
    mock_res.getcode.return_value = 200
    mock_res.__enter__.return_value = mock_res

    speakers_data = [
        {
            "name": "ずんだもん",
            "speaker_uuid": "uuid-zunda",
            "styles": [{"name": "ノーマル", "id": 1}, {"name": "あまあま", "id": 3}],
        }
    ]
    mock_res.read.return_value = json.dumps(speakers_data).encode("utf-8")
    mock_urlopen.return_value = mock_res

    # Use a dummy is_available returning True to allow communication
    with patch.object(VoiceVoxClient, "is_available", return_value=True):
        result = vv_client.get_speakers(force_refresh=True)

    assert len(result) == 1
    assert result[0]["name"] == "ずんだもん"
    assert vv_client._speakers_cache == speakers_data


def test_get_style_info(vv_client):
    # Setup cache
    vv_client._speakers_cache = [
        {
            "name": "ずんだもん",
            "styles": [{"name": "ノーマル", "id": 1}, {"name": "あまあま", "id": 3}],
        }
    ]

    # Test valid ID
    info1 = vv_client.get_style_info(1)
    assert info1 == {"speaker_name": "ずんだもん", "style_name": "ノーマル"}

    info3 = vv_client.get_style_info(3)
    assert info3 == {"speaker_name": "ずんだもん", "style_name": "あまあま"}

    # Test invalid ID
    assert vv_client.get_style_info(999) is None


def test_get_style_info_no_cache(vv_client):
    vv_client._speakers_cache = None
    assert vv_client.get_style_info(1) is None
