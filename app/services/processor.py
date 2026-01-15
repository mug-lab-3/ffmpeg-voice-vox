import json
import os
from datetime import datetime, timezone
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.core.database import db_manager, Transcription


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

            for transcription in reversed(
                db_logs
            ):  # Add oldest first for list append order
                filename = transcription.output_path
                duration = transcription.audio_duration

                # Verify file existence if it was already generated
                if filename and duration >= 0:
                    full_path = os.path.normpath(os.path.join(output_dir, filename))
                    if not os.path.exists(full_path):
                        # File missing on disk, but DB says it exists -> Delete from DB and skip
                        print(
                            f"  -> File MISSING on disk: {filename}. Resetting status for record ID {transcription.id}."
                        )
                        db_manager.update_audio_info(transcription.id, None, -1.0)
                        filename = None
                        duration = -1.0
                    else:
                        print(f"  -> File OK: {filename}")

                log_entry = {
                    "id": transcription.id,
                    "timestamp": (
                        f"{transcription.timestamp}Z"
                        if not transcription.timestamp.endswith("Z")
                        else transcription.timestamp
                    ).replace(" ", "T"),
                    "text": transcription.text,
                    "duration": f"{duration:.2f}s",
                    "config": {
                        "speaker_id": transcription.speaker_id,
                        "speed_scale": transcription.speed_scale,
                        "pitch_scale": transcription.pitch_scale,
                        "intonation_scale": transcription.intonation_scale,
                        "volume_scale": transcription.volume_scale,
                        "pre_phoneme_length": transcription.pre_phoneme_length,
                        "post_phoneme_length": transcription.post_phoneme_length,
                        "pause_length_scale": transcription.pause_length_scale,
                    },
                    "speaker_info": self._format_speaker_info(
                        transcription.speaker_id,
                        transcription.speaker_name,
                        transcription.speaker_style,
                    ),
                    "filename": (
                        filename
                        if (filename and duration >= 0)
                        else f"pending_{transcription.id}.wav"
                    ),
                    "is_generated": (duration >= 0),
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

    def _prepare_query_data(
        self, text: str, speaker_id: int, config_dict: dict
    ) -> dict:
        """
        Executes audio_query and applies provided config scales.
        Returns query_data directly from VOICEVOX if successful, or None if failed.
        Also calculates kana and phonemes.
        """
        if not self.vv_client.is_available():
            print("[Processor] VOICEVOX is not available for query.")
            return None

        try:
            query_data = self.vv_client.audio_query(text, speaker_id)

            # Apply parameters from config_dict
            query_data["speedScale"] = float(config_dict.get("speed_scale", 1.0))
            query_data["pitchScale"] = float(config_dict.get("pitch_scale", 0.0))
            query_data["intonationScale"] = float(
                config_dict.get("intonation_scale", 1.0)
            )
            query_data["volumeScale"] = float(config_dict.get("volume_scale", 1.0))
            query_data["prePhonemeLength"] = float(
                config_dict.get("pre_phoneme_length", 0.1)
            )
            query_data["postPhonemeLength"] = float(
                config_dict.get("post_phoneme_length", 0.1)
            )
            query_data["pauseLengthScale"] = float(
                config_dict.get("pause_length_scale", 1.0)
            )

            # Extract derived attributes
            kana = query_data.get("kana")
            phonemes = self._extract_phonemes(query_data)

            # Ensure they are serializable (especially in test mocks)
            query_data["_extra_kana"] = str(kana) if kana is not None else None

            # Strong serializability check for phonemes (to block MagicMock in tests)
            try:
                # Store it as JSON string right here to be absolutely sure
                query_data["_extra_phonemes_json"] = json.dumps(phonemes)
            except (TypeError, OverflowError):
                query_data["_extra_phonemes_json"] = "[]"

            return query_data
        except Exception as e:
            print(f"[Processor] Error preparing query data: {e}")
            return None

    def _handle_transcription(self, data):
        text = data["text"]
        print(f"Processing: {text}")

        # 1. Prepare Config (Current global UI state for NEW item)
        # 2. Add to DB first (Pending state) using Model
        style_info = self.vv_client.get_style_info(speaker_id)

        t = Transcription(
            text=text,
            speaker_id=speaker_id,
            speaker_name=style_info["speaker_name"] if style_info else None,
            speaker_style=style_info["style_name"] if style_info else None,
            **current_config,
        )

        db_id = db_manager.add_transcription(t)

        generated_file = None
        actual_duration = -1.0
        timing = config.get("synthesis.timing", "immediate")

        if timing == "immediate":
            try:
                # 4. Synthesis (Now triggers audio_query inside synthesize_item if we refactor it,
                # but for immediate we still need to call something. Let's use synthesize_item logic)
                generated_file, actual_duration = self.synthesize_item(db_id)
                print(
                    f"  -> Immediate Generated: {generated_file} ({actual_duration:.2f}s)"
                )

            except Exception as e:
                print(f"Synthesis Error: {e}")
                generated_file = "Error"
        else:
            if timing == "on_demand":
                print(f"  -> Delayed (on_demand): {db_id}")
            else:
                print("  -> Synthesis Skipped (Disabled)")

        # 7. Add to UI logs
        self._add_log_from_db(
            db_id, text, actual_duration, generated_file, speaker_id, current_config
        )

    def _extract_phonemes(self, query_data: dict) -> list:
        """Extract phonemes with cumulative start times (seconds)."""
        # Type guard for mocks in tests
        if not hasattr(query_data, "get"):
            return []

        phonemes = []
        try:
            current_time = float(query_data.get("prePhonemeLength", 0.1))
            speed_scale = float(query_data.get("speedScale", 1.0))

            for phrase in query_data.get("accent_phrases", []):
                # Another guard for nested mocks
                if not hasattr(phrase, "get"):
                    continue
                for mora in phrase.get("moras", []):
                    if not hasattr(mora, "get"):
                        continue
                    # Consonant
                    if mora.get("consonant"):
                        phonemes.append(
                            {"t": round(current_time, 3), "p": str(mora["consonant"])}
                        )
                        current_time += (
                            mora.get("consonant_length") or 0.0
                        ) / speed_scale

                    # Vowel
                    if mora.get("vowel"):
                        phonemes.append(
                            {"t": round(current_time, 3), "p": str(mora["vowel"])}
                        )
                        current_time += (mora.get("vowel_length") or 0.0) / speed_scale

                # Pause after accent phrase
                pause_mora = phrase.get("pause_mora")
                if pause_mora and hasattr(pause_mora, "get"):
                    pause_len = (pause_mora.get("vowel_length") or 0.0) / speed_scale
                    pause_len *= float(query_data.get("pauseLengthScale", 1.0))
                    current_time += pause_len
        except (AttributeError, TypeError, ValueError):
            return []

        return phonemes

    def synthesize_item(self, db_id: int):
        """Perform synthesis for an existing DB record and save the file."""
        # 1. Fetch exactly what we need from DB using Model
        t = db_manager.get_transcription(db_id)
        if not t:
            raise ValueError(f"Record not found: {db_id}")

        if t.audio_duration > 0:
            return t.output_path, t.audio_duration

        print(f"On-demand Synthesis: ID={db_id} Text='{t.text}'")

        # 2. Reconstruct parameters from Model
        text = t.text
        speaker_id = t.speaker_id
        item_config = t.model_dump(
            include={
                "speed_scale",
                "pitch_scale",
                "intonation_scale",
                "volume_scale",
                "pre_phoneme_length",
                "post_phoneme_length",
                "pause_length_scale",
            }
        )

        # 3. VoiceVox Query & Synthesis using common logic
        try:
            query_data = self._prepare_query_data(text, speaker_id, item_config)
            if not query_data:
                raise RuntimeError("Failed to prepare query data (VOICEVOX offline?)")

            new_kana = query_data["_extra_kana"]
            new_phonemes = query_data["_extra_phonemes_json"]

            audio_data = self.vv_client.synthesis(query_data, speaker_id)
        except Exception as e:
            print(f"[Processor] Synthesis CRITICAL Error for ID {db_id}: {e}")
            raise

        # 4. Generate Filename & Save
        wav_filename = self._generate_filename(db_id, text, item_config)
        actual_duration = self.audio_manager.save_audio(audio_data, wav_filename)
        generated_file = wav_filename

        # 5. Update DB (including kana/phonemes)
        db_manager.update_audio_info(
            db_id,
            generated_file,
            actual_duration,
            kana=new_kana,
            phonemes=new_phonemes,
        )

        # 6. Update UI Log Cache
        for log in self.received_logs:
            if log.get("id") == db_id:
                log["filename"] = generated_file
                log["duration"] = f"{actual_duration:.2f}s"
                log["is_generated"] = True
                break

        from app.core.events import event_manager

        event_manager.publish("log_update", {})

        return generated_file, actual_duration

    def _generate_filename(self, db_id: int, text: str, config_dict: dict) -> str:
        """Generates filename: {id}_{hash}_{prefix}.wav"""
        import re
        import hashlib
        import json

        # Sanitize text for filename
        safe_text = re.sub(r'[\\/:*?"<>|]+', "", text)
        safe_text = safe_text.replace("\n", "").replace("\r", "")
        prefix_text = safe_text[:8]

        # Prepare hash source
        hash_source = {"text": text}
        if config_dict:
            relevant_keys = [
                "speaker_id",
                "speed_scale",
                "pitch_scale",
                "intonation_scale",
                "volume_scale",
                "pre_phoneme_length",
                "post_phoneme_length",
                "pause_length_scale",
            ]
            for key in relevant_keys:
                if key in config_dict:
                    hash_source[key] = config_dict[key]

        # Calculate Hash
        hash_str = json.dumps(hash_source, sort_keys=True, ensure_ascii=False)
        sha1_hash = hashlib.sha1(hash_str.encode("utf-8")).hexdigest()[:8]

        return f"{db_id:03d}_{sha1_hash}_{prefix_text}.wav"

    def _add_log_from_db(self, t: Transcription):
        log_entry = {
            "id": t.id,
            "timestamp": f"{datetime.now(timezone.utc).isoformat()}Z",
            "text": t.text,
            "duration": f"{t.audio_duration:.2f}s",
            "config": {
                "speaker_id": t.speaker_id,
                "speed_scale": t.speed_scale,
                "pitch_scale": t.pitch_scale,
                "intonation_scale": t.intonation_scale,
                "volume_scale": t.volume_scale,
                "pre_phoneme_length": t.pre_phoneme_length,
                "post_phoneme_length": t.post_phoneme_length,
                "pause_length_scale": t.pause_length_scale,
            },
            "filename": (
                t.output_path
                if (t.output_path and t.audio_duration >= 0)
                else f"pending_{t.id}.wav"
            ),
            "speaker_info": self._format_speaker_info(
                t.speaker_id, t.speaker_name, t.speaker_style
            ),
            "is_generated": (t.audio_duration >= 0),
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
        # 1. Fetch Current Settings from DB Model to preserve them
        old_filename = None
        t = db_manager.get_transcription(db_id)

        if t:
            old_filename = t.output_path
            speaker_id = t.speaker_id
        else:
            # If not in DB, try to find in cache just to get current state (useful for tests)
            print(f"[Processor] Record {db_id} not found in DB for text update.")
            speaker_id = config.get("synthesis.speaker_id", 1)
            for log in self.received_logs:
                if log.get("id") == db_id:
                    old_filename = log.get("filename")
                    speaker_id = log.get("config", {}).get("speaker_id", 1)
                    break

        # 2. Update Database (Reset attributes to None until next synthesis)
        print(f"[Processor] Updating text for ID {db_id}: '{new_text}'")
        db_manager.update_transcription_text(db_id, new_text, kana=None, phonemes=None)
        # Minor delay or explicit close is not available on db_manager easily,
        # so we rely on the fact that update_transcription_text should release it.

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
                log["duration"] = "-1.00s"  # Reset duration
                log["filename"] = f"pending_{db_id}.wav"  # Reset filename
                log["is_generated"] = False
                found = True
                break

        from app.core.events import event_manager

        event_manager.publish("log_update", {})

        if not found:
            # Should reload if not found, but it should be there.
            pass

    def _format_speaker_info(
        self, speaker_id: int, name: str = None, style: str = None
    ) -> str:
        """Helper to format speaker info string. Prefers provided name/style, then fallback to cache."""
        if name and style:
            return f"{name}({style})"

        # Fallback to cache if database didn't have it (old records)
        info = self.vv_client.get_style_info(speaker_id)
        if info:
            return f"{info['speaker_name']}({info['style_name']})"

        return f"ID:{speaker_id}"
