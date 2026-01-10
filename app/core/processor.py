import json
from datetime import datetime
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager

class StreamProcessor:
    def __init__(self, voicevox_client: VoiceVoxClient, audio_manager: AudioManager):
        self.vv_client = voicevox_client
        self.audio_manager = audio_manager
        self.received_logs = []

    def process_stream(self, stream_iterator):
        buffer = ""
        for chunk in stream_iterator:
            if chunk:
                buffer += chunk.decode('utf-8', errors='ignore')
                
                while '}' in buffer:
                    brace_index = buffer.find('}')
                    json_str = buffer[:brace_index+1]
                    buffer = buffer[brace_index+1:]
                    
                    try:
                        self._process_json_chunk(json_str)
                    except Exception as e:
                        print(f"Error processing chunk: {e}")
                        # If error is severe, we might want to break, but for now continue stream
                        continue

    def _process_json_chunk(self, json_str):
        try:
            data = json.loads(json_str)
            print(f"Received JSON: {json.dumps(data, ensure_ascii=False)}")
            
            if "text" in data and "start" in data and "end" in data:
                self._handle_transcription(data)
            else:
                print("Skipping: Invalid data format")
                
        except json.JSONDecodeError:
            print("JSON Decode Error (chunk)")

    def _handle_transcription(self, data):
        text = data["text"]
        start = data["start"]
        end = data["end"]
        
        print(f"Processing: [{start}ms - {end}ms] {text}")
        
        generated_file = None
        actual_duration = 0.0
        
        if config.get("system.is_synthesis_enabled", True):
            try:
                # 1. Audio Query
                speaker_id = config.get("synthesis.speaker_id", 1)
                query_data = self.vv_client.audio_query(text, speaker_id)
                
                # 2. Synthesis
                audio_data = self.vv_client.synthesis(query_data, speaker_id)
                
                # 3. Save
                speaker_name = self.vv_client.get_speakers().get(speaker_id, f"ID{speaker_id}")
                generated_file, actual_duration = self.audio_manager.save_audio(
                   audio_data, text, speaker_name, start, end
                )
                
                print(f"  -> Generated: {generated_file} ({actual_duration:.2f}s)")
                
            except Exception as e:
                print(f"Synthesis Error: {e}")
                generated_file = "Error"
        else:
            print("  -> Synthesis Skipped (Disabled)")
            
        # Log entry
        self._add_log(text, actual_duration, generated_file)

    def _add_log(self, text, duration, filename):
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "text": text,
            "duration": f"{duration:.2f}s",
            "config": config.get("synthesis"), 
            "filename": filename if filename else "Error"
        }
        
        if len(self.received_logs) > 50:
            self.received_logs.pop(0)
        self.received_logs.append(log_entry)

    def get_logs(self):
        return self.received_logs

    def delete_log(self, filename):
        self.received_logs = [log for log in self.received_logs if log.get('filename') != filename]

# Singleton-alike instance creation would happen in app factory or DI container
