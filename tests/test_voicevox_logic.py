import pytest
import json
from unittest.mock import MagicMock, patch
from app.core.voicevox import VoiceVoxClient, VoiceVoxSpeaker, VoiceVoxStyle


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
    assert isinstance(result[0], VoiceVoxSpeaker)
    assert result[0].name == "ずんだもん"
    assert result[0].styles[0].id == 1


def test_get_style_info(vv_client):
    # Setup cache using proper Models
    vv_client._speakers_cache = [
        VoiceVoxSpeaker(
            name="ずんだもん",
            speaker_uuid="uuid-zunda",
            styles=[
                VoiceVoxStyle(name="ノーマル", id=1),
                VoiceVoxStyle(name="あまあま", id=3),
            ],
        )
    ]

    # Test valid ID
    info1 = vv_client.get_style_info(1)
    assert info1 is not None
    assert info1.speaker_name == "ずんだもん"
    assert info1.style_name == "ノーマル"

    # Test another valid ID
    info2 = vv_client.get_style_info(3)
    assert info2 is not None
    assert info2.style_name == "あまあま"

    # Test invalid ID
    assert vv_client.get_style_info(999) is None
