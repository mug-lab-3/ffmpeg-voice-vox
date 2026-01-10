import json
import urllib.request
import urllib.parse
from app.config import config

class VoiceVoxClient:
    def __init__(self):
        pass

    @property
    def base_url(self):
        host = config.get("voicevox.host", "127.0.0.1")
        port = config.get("voicevox.port", 50021)
        return f"http://{host}:{port}"

    def get_speakers(self):
        # NOTE: In a real app we might want to fetch this from the API dynamically,
        # but for now we keep the existing hardcoded mapping or fetch it if needed.
        # The original code had a hardcoded map. Let's start with that map but maybe expose an API to fetch it later.
        # For now, we return the static list from the original requirements to avoid breaking changes if the API is offline during init.
        # Actually, let's keep the static map in a better place or just return it here.
        # Original map:
        return {
            1: "ずんだもん",
            2: "四国めたん",
            8: "春日部つむぎ",
            9: "波音リツ"
        }

    def audio_query(self, text: str, speaker_id: int) -> dict:
        url = f"{self.base_url}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker_id}"
        req = urllib.request.Request(url, method='POST')
        with urllib.request.urlopen(req) as res:
            return json.load(res)

    def synthesis(self, query_data: dict, speaker_id: int) -> bytes:
        # Apply config overrides
        query_data['speedScale'] = config.get("synthesis.speed_scale", 1.0)
        query_data['pitchScale'] = config.get("synthesis.pitch_scale", 0.0)
        query_data['intonationScale'] = config.get("synthesis.intonation_scale", 1.0)
        query_data['volumeScale'] = config.get("synthesis.volume_scale", 1.0)

        url = f"{self.base_url}/synthesis?speaker={speaker_id}"
        json_data = json.dumps(query_data).encode('utf-8')
        req = urllib.request.Request(url, data=json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as res:
            return res.read()
