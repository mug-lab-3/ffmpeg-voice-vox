import json
import os
from datetime import datetime, timezone
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
            print(f"  -> Loading from: {output_dir}")

            for entry in reversed(db_logs):  # Add oldest first for list append order
                filename = entry["output_path"]
                duration = entry["audio_duration"]

                # Verify file existence if it was already generated
                if filename and duration > 0:
                    full_path = os.path.normpath(os.path.join(output_dir, filename))
                    if not os.path.exists(full_path):
                        # File missing on disk, but DB says it exists -> Delete from DB and skip
                        print(
                            f"  -> File MISSING on disk: {filename}. Deleting record ID {entry['id']} from DB."
                        )
                        db_manager.delete_log(entry["id"])
                        continue
                    else:
                        print(f"  -> File OK: {filename}")

                log_entry = {
                    "id": entry["id"],
                    "timestamp": (
                        f"{entry['timestamp']}Z"
                        if not entry["timestamp"].endswith("Z")
                        else entry["timestamp"]
                    ).replace(" ", "T"),
                    "text": entry["text"],
                    "duration": f"{duration:.2f}s",
                    "config": {
                        "speaker_id": entry["speaker_id"],
                        "speed_scale": entry["speed_scale"],
                        "pitch_scale": entry["pitch_scale"],
                        "intonation_scale": entry["intonation_scale"],
                        "volume_scale": entry["volume_scale"],
                        "pre_phoneme_length": entry["pre_phoneme_length"],
                        "post_phoneme_length": entry["post_phoneme_length"],
                    },
                    "filename": (
                        filename
                        if (filename and duration > 0)
                        else f"pending_{entry['id']}.wav"
                    ),
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
                buffer += chunk.decode("utf-8", errors="ignore")

                while "}" in buffer:
                    brace_index = buffer.find("}")
                    json_str = buffer[: brace_index + 1]
                    buffer = buffer[brace_index + 1 :]

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
            audio_duration=0.0,
        )

        generated_file = None
        actual_duration = 0.0

        timing = config.get("synthesis.timing", "immediate")

        if config.get("system.is_synthesis_enabled", True) and timing == "immediate":
            try:
                # 3. Audio Query
                query_data = self.vv_client.audio_query(text, speaker_id)

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
            if timing == "on_demand":
                print(f"  -> Delayed (on_demand): {db_id}")
            else:
                print("  -> Synthesis Skipped (Disabled)")

        # 7. Add to UI logs (or update existing)
        self._add_log_from_db(
            db_id, text, actual_duration, generated_file, speaker_id, current_config
        )

    def synthesize_item(self, db_id: int):
        """Perform synthesis for an existing DB record and save the file."""
        # 1. Fetch exactly what we need from DB
        with db_manager._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM transcriptions WHERE id = ?", (db_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Record not found: {db_id}")
            record = dict(row)

        if record["audio_duration"] > 0:
            return record["output_path"], record["audio_duration"]

        print(f"On-demand Synthesis: ID={db_id} Text='{record['text']}'")

        # 2. Reconstruct query config
        text = record["text"]
        speaker_id = int(record["speaker_id"] or 1)

        # 3. VoiceVox Query & Synthesis
        try:
            query_data = self.vv_client.audio_query(text, speaker_id)

            # Apply scales with default fallback to avoid None errors
            query_data["speedScale"] = float(record["speed_scale"] or 1.0)
            query_data["pitchScale"] = float(record["pitch_scale"] or 0.0)
            query_data["intonationScale"] = float(record["intonation_scale"] or 1.0)
            query_data["volumeScale"] = float(record["volume_scale"] or 1.0)
            query_data["prePhonemeLength"] = float(record["pre_phoneme_length"] or 0.1)
            query_data["postPhonemeLength"] = float(
                record["post_phoneme_length"] or 0.1
            )

            audio_data = self.vv_client.synthesis(query_data, speaker_id)
        except Exception as e:
            print(f"[Processor] Synthesis CRITICAL Error for ID {db_id}: {e}")
            import traceback

            traceback.print_exc()
            raise

        # 4. Save
        generated_file, actual_duration = self.audio_manager.save_audio(
            audio_data, text, db_id
        )

        # 5. Update DB
        db_manager.update_audio_info(db_id, generated_file, actual_duration)

        # 6. Update UI Log Cache
        for log in self.received_logs:
            if log.get("id") == db_id:
                log["filename"] = generated_file
                log["duration"] = f"{actual_duration:.2f}s"
                break

        from app.core.events import event_manager

        event_manager.publish("log_update", {})

        return generated_file, actual_duration

    def _add_log_from_db(
        self,
        db_id: int,
        text: str,
        duration: float,
        filename: str,
        speaker_id: int,
        log_config: dict,
    ):

        log_entry = {
            "id": db_id,
            "timestamp": f"{datetime.now(timezone.utc).isoformat()}Z",
            "text": text,
            "duration": f"{duration:.2f}s",
            "config": log_config.copy(),
            "filename": (
                filename
                if (filename and filename != "Pending" and duration > 0)
                else f"pending_{db_id}.wav"
            ),
        }

        if len(self.received_logs) >= 50:
            self.received_logs.pop(0)
        self.received_logs.append(log_entry)

        from app.core.events import event_manager

        event_manager.publish("log_update", {})

    def get_logs(self):
        return self.received_logs

    def delete_log(self, db_id: int):
        """Removes from UI list AND Database by ID."""
        # 1. Delete from DB
        print(
            f"[Processor] Deleting record ID {db_id} from DB (triggered by UI delete)"
        )
        # We need to find the filename before deleting from cache to return it
        filename = None
        for log in self.received_logs:
            if log.get("id") == db_id:
                filename = log.get("filename")
                break

        db_manager.delete_log(db_id)

        # 2. Cache deletion
        self.received_logs = [
            log for log in self.received_logs if log.get("id") != db_id
        ]

        from app.core.events import event_manager

        event_manager.publish("log_update", {})

        return filename

    def update_log_text(self, db_id: int, new_text: str):
        """Updates text for a log entry by ID, deletes old audio if exists, and resets state."""
        # 1. Find Current Cache Entry to check for old filename
        old_filename = None
        for log in self.received_logs:
            if log.get("id") == db_id:
                old_filename = log.get("filename")
                break

        # 2. Update Database
        print(f"[Processor] Updating text for ID {db_id}: '{new_text}'")
        db_manager.update_transcription_text(db_id, new_text)

        # 3. Delete physical file if it was a real file
        if old_filename and not old_filename.startswith("pending_"):
            print(f"[Processor] Deleting old audio file: {old_filename}")
            try:
                self.audio_manager.delete_file(old_filename)
            except Exception as e:
                print(f"[Processor] Error deleting file {old_filename}: {e}")

        # 4. Update Cache (Reset to pending state)
        found = False
        for log in self.received_logs:
            if log.get("id") == db_id:
                log["text"] = new_text
                log["duration"] = "0.00s"  # Reset duration
                log["filename"] = f"pending_{db_id}.wav"  # Reset filename
                found = True
                break

        if not found:
            # Should reload if not found, but it should be there.
            pass

        from app.core.events import event_manager

        event_manager.publish("log_update", {})
