import json
import urllib.request
import urllib.parse
from app.config import config


class VoiceVoxClient:
    def __init__(self):
        self._speakers_cache = None

    @property
    def base_url(self):
        host = config.get("voicevox.host", "127.0.0.1")
        port = config.get("voicevox.port", 50021)
        return f"http://{host}:{port}"

    def is_available(self) -> bool:
        try:
            url = f"{self.base_url}/version"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as res:
                return res.getcode() == 200
        except:
            return False

    def get_speakers(self, force_refresh: bool = False):
        """
        Fetch speakers from VOICEVOX API.
        Returns the raw list from API or empty list if unavailable.
        """
        if self._speakers_cache is not None and not force_refresh:
            return self._speakers_cache

        # Check availability first to avoid timeout wait if offline
        if not self.is_available():
            return []

        try:
            url = f"{self.base_url}/speakers"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1) as res:
                if res.getcode() == 200:
                    self._speakers_cache = json.load(res)
                    return self._speakers_cache
        except Exception as e:
            print(f"[VoiceVoxClient] Error fetching speakers: {e}")

        return []

    def get_style_info(self, style_id: int) -> dict:
        """
        Returns style information (speaker name and style name) using CACHE ONLY.
        Returns None if cache is empty or ID not found.
        """
        if self._speakers_cache is None:
            return None

        for s in self._speakers_cache:
            for style in s.get("styles", []):
                if style.get("id") == style_id:
                    return {"speaker_name": s["name"], "style_name": style["name"]}
        return None

    def audio_query(self, text: str, speaker_id: int) -> dict:
        url = f"{self.base_url}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker_id}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req) as res:
            return json.load(res)

    def synthesis(self, query_data: dict, speaker_id: int) -> bytes:
        # Apply config overrides
        query_data["speedScale"] = config.get("synthesis.speed_scale", 1.0)
        query_data["pitchScale"] = config.get("synthesis.pitch_scale", 0.0)
        query_data["intonationScale"] = config.get("synthesis.intonation_scale", 1.0)
        query_data["volumeScale"] = config.get("synthesis.volume_scale", 1.0)
        query_data["prePhonemeLength"] = config.get("synthesis.pre_phoneme_length", 0.1)
        query_data["postPhonemeLength"] = config.get(
            "synthesis.post_phoneme_length", 0.1
        )
        query_data["pauseLengthScale"] = config.get("synthesis.pause_length_scale", 1.0)

        # Quality settings fixed
        query_data["outputSamplingRate"] = 48000
        query_data["outputStereo"] = True

        url = f"{self.base_url}/synthesis?speaker={speaker_id}"
        json_data = json.dumps(query_data).encode("utf-8")
        req = urllib.request.Request(url, data=json_data, method="POST")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req) as res:
            return res.read()
