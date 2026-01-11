import json
import os
from datetime import datetime
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.core.database import db_manager

class StreamProcessor:
    def __init__(self, voicevox_client: VoiceVoxClient, audio_manager: AudioManager):
        self.vv_client = voicevox_client
        self.audio_manager = audio_manager
        self.received_logs = []
        
        # Load history from Database
        self._load_history()

    def _load_history(self):
        try:
            print("Loading history from database...")
            db_logs = db_manager.get_recent_logs(limit=50)
            output_dir = self.audio_manager.get_output_dir()
            
            for entry in reversed(db_logs): # Add oldest first for list append order
                filename = entry["output_path"]
                duration = entry["audio_duration"]
                
                # Verify file existence if it's supposed to exist
                if filename and duration > 0:
                    full_path = os.path.join(output_dir, filename)
                    if not os.path.exists(full_path):
                        print(f"  -> File missing: {filename}. Marking as non-generated.")
                        db_manager.update_audio_info(entry["id"], filename, 0.0)
                        duration = 0.0
                
                log_entry = {
                    "id": entry["id"],
                    "timestamp": entry["timestamp"].split()[1] if ' ' in entry["timestamp"] else entry["timestamp"], 
                    "text": entry["text"],
                    "duration": f"{duration:.2f}s",
                    "config": {
                        "speaker_id": entry["speaker_id"],
                        "speed_scale": entry["speed_scale"],
                        "pitch_scale": entry["pitch_scale"],
                        "intonation_scale": entry["intonation_scale"],
                        "volume_scale": entry["volume_scale"],
                        "pre_phoneme_length": entry["pre_phoneme_length"],
                        "post_phoneme_length": entry["post_phoneme_length"]
                    },
                    "filename": filename if duration > 0 else "Pending"
                }
                self.received_logs.append(log_entry)
                
        except Exception as e:
            print(f"Error loading history from DB: {e}")

    def reload_history(self):
        """Clear current logs and reload."""
        print("Reloading history logs...")
        self.received_logs = []
        self._load_history()

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
                        continue

    def _process_json_chunk(self, json_str):
        try:
            data = json.loads(json_str)
            if "text" in data:
                self._handle_transcription(data)
        except json.JSONDecodeError:
            pass

    def _handle_transcription(self, data):
        text = data["text"]
        print(f"Processing: {text}")
        
        # 1. Prepare Config
        current_config = config.get("synthesis")
        speaker_id = config.get("synthesis.speaker_id", 1)
        
        # 2. Add to DB first (Pending state)
        db_id = db_manager.add_transcription(
            text=text,
            speaker_id=speaker_id,
            config_dict=current_config,
            output_path=None,
            audio_duration=0.0
        )

        generated_file = None
        actual_duration = 0.0
        
        if config.get("system.is_synthesis_enabled", True):
            try:
                # 3. Audio Query
                query_data = self.vv_client.audio_query(text, speaker_id)
                # (Future: Apply scales from current_config here if not already handled by VV client)
                
                # 4. Synthesis
                audio_data = self.vv_client.synthesis(query_data, speaker_id)
                
                # 5. Save with DB ID
                generated_file, actual_duration = self.audio_manager.save_audio(
                   audio_data, text, db_id
                )
                
                # 6. Update DB with file info
                db_manager.update_audio_info(db_id, generated_file, actual_duration)
                print(f"  -> Generated: {generated_file} ({actual_duration:.2f}s)")
                
            except Exception as e:
                print(f"Synthesis Error: {e}")
                generated_file = "Error"
        else:
            print("  -> Synthesis Skipped (Disabled)")

        # 7. Add to UI logs (or update existing)
        self._add_log_from_db(db_id, text, actual_duration, generated_file, speaker_id, current_config)

    def _add_log_from_db(self, db_id, text, duration, filename, speaker_id, log_config):
        log_entry = {
            "id": db_id,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "text": text,
            "duration": f"{duration:.2f}s",
            "config": log_config.copy(), 
            "filename": filename if duration > 0 else "Pending"
        }
        
        if len(self.received_logs) >= 50:
            self.received_logs.pop(0)
        self.received_logs.append(log_entry)
        
        from app.core.events import event_manager
        event_manager.publish("log_update", {})

    def get_logs(self):
        return self.received_logs

    def delete_log(self, filename):
        # We might need to find the ID if we want to delete from DB too
        # For now, keep it simple UI-side
        self.received_logs = [log for log in self.received_logs if log.get('filename') != filename]

# Singleton-alike instance creation would happen in app factory or DI container
