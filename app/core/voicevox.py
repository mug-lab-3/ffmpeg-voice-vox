import json
import urllib.request
import urllib.parse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.config.schemas import VoiceVoxConfig


class VoiceVoxStyle(BaseModel):
    name: str
    id: int


class VoiceVoxSpeaker(BaseModel):
    name: str
    speaker_uuid: str
    styles: List[VoiceVoxStyle]


class VoiceVoxStyleInfo(BaseModel):
    speaker_name: str
    style_name: str


class VoiceVoxAudioQuery(BaseModel):
    """VOICEVOX AudioQuery structure with key parameters."""

    accent_phrases: List[Dict[str, Any]]
    speedScale: float
    pitchScale: float
    intonationScale: float
    volumeScale: float
    prePhonemeLength: float
    postPhonemeLength: float
    pauseLengthScale: float = 1.0
    outputSamplingRate: int
    outputStereo: bool
    kana: Optional[str] = None

    def model_dump_json_scaled(self) -> str:
        """Utility to export JSON for synthesis."""
        return self.model_dump_json()


class VoiceVoxClient:
    def __init__(self, config: VoiceVoxConfig):
        self.config = config
        self._speakers_cache: Optional[List[VoiceVoxSpeaker]] = None

    @property
    def base_url(self) -> str:
        host = self.config.host
        port = self.config.port
        return f"http://{host}:{port}"

    def is_available(self) -> bool:
        try:
            url = f"{self.base_url}/version"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as res:
                return res.getcode() == 200
        except:
            return False

    def get_speakers(self, force_refresh: bool = False) -> List[VoiceVoxSpeaker]:
        """Fetch speakers and return as strongly typed models."""
        if self._speakers_cache is not None and not force_refresh:
            return self._speakers_cache

        if not self.is_available():
            return []

        try:
            url = f"{self.base_url}/speakers"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as res:
                if res.getcode() == 200:
                    raw_data = json.load(res)
                    self._speakers_cache = [VoiceVoxSpeaker(**s) for s in raw_data]
                    return self._speakers_cache
        except Exception as e:
            print(f"[VoiceVoxClient] Error fetching speakers: {e}")

        return []

    def get_style_info(self, style_id: int) -> Optional[VoiceVoxStyleInfo]:
        """Returns style information using models."""
        if self._speakers_cache is None:
            # Try to load if empty but available
            self.get_speakers()
            if self._speakers_cache is None:
                return None

        for s in self._speakers_cache:
            for style in s.styles:
                if style.id == style_id:
                    return VoiceVoxStyleInfo(speaker_name=s.name, style_name=style.name)
        return None

    def audio_query(self, text: str, speaker_id: int) -> VoiceVoxAudioQuery:
        """Performs audio_query and returns a typed model."""
        url = f"{self.base_url}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker_id}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req) as res:
            raw_data = json.load(res)
            return VoiceVoxAudioQuery(**raw_data)

    def synthesis(self, query: VoiceVoxAudioQuery, speaker_id: int) -> bytes:
        """Synthesize audio using the AudioQuery model."""
        # Quality settings fixed
        query.outputSamplingRate = 48000
        query.outputStereo = True

        url = f"{self.base_url}/synthesis?speaker={speaker_id}"
        json_data = query.model_dump_json().encode("utf-8")
        req = urllib.request.Request(url, data=json_data, method="POST")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req) as res:
            return res.read()
