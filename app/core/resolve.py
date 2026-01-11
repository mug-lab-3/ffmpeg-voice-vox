import sys
import os
import platform
import threading
import time
import multiprocessing
import importlib
import datetime
import traceback

# Utility Constants
LOG_DIR = "logs"
RESOLVE_MONITOR_LOG = "resolve_monitor.log"
RESOLVE_CLIENT_LOG = "resolve.log"

DEFAULT_VIDEO_TRACK = 2
DEFAULT_AUDIO_TRACK = 1

def get_resolve_module_path():
    """Returns the expected path for DaVinci Resolve scripting modules based on OS."""
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.getenv('PROGRAMDATA', ''), 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules')
    elif system == "Darwin":
        return "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
    return None

def normalize_fps(fps_val):
    """
    Normalizes FPS values to handle standard video frame rates.
    Rounds 23.976->24, 29.97->30, 59.94->60.
    """
    try:
        if not isinstance(fps_val, (int, float)):
            fps_val = float(fps_val)

        if 29.0 < fps_val < 30.0: return 30
        elif 59.0 < fps_val < 60.0: return 60
        elif 23.0 < fps_val < 24.0: return 24

        return int(round(fps_val))
    except (ValueError, TypeError):
        return 0

def _log_monitor(msg):
    """Standalone logger for the monitor process."""
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        log_file = os.path.join(LOG_DIR, RESOLVE_MONITOR_LOG)

        with open(log_file, "a", encoding="utf-8") as f:
            dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{dt}] {msg}\n")
    except:
        pass

# Standalone function for the separate process
def monitor_resolve_process(shared_status, running_event):
    """
    Runs in a separate process.
    Continuously checks if DaVinci Resolve is reachable.
    Updates shared_status (0=No, 1=Yes).
    """
    _log_monitor("Monitor process started")

    last_status = None # None indicates startup/unknown
    dvr_module = None

    while running_event.is_set():
        try:
            success = False

            # STEP 0: Check if Resolve process even exists before doing heavy API calls
            is_running = False
            try:
                import psutil
                # Iterate over all running processes
                for proc in psutil.process_iter(['name']):
                    try:
                        name = proc.info['name']
                        if name and "Resolve" in name:
                            is_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except ImportError:
                _log_monitor("psutil not found, assuming Resolve is running to trigger probe")
                is_running = True
            except Exception as e:
                _log_monitor(f"Process check error: {e}")
                is_running = True # If check fails, fall back to probe

            if is_running:
                try:
                    # Setup path just in case (only once)
                    expected_path = get_resolve_module_path()

                    if expected_path and os.path.exists(expected_path) and expected_path not in sys.path:
                        sys.path.append(expected_path)

                    # Try to import/reload only if not connected or not yet imported
                    if dvr_module is None:
                        try:
                            import DaVinciResolveScript as dvr
                            dvr_module = dvr
                        except ImportError:
                            pass
                    elif not last_status: # If module exists but was disconnected, try reload
                        try:
                            importlib.reload(dvr_module)
                        except:
                            pass

                    if dvr_module:
                        try:
                            resolve = dvr_module.scriptapp("Resolve")
                            if resolve:
                                success = True
                        except:
                            pass

                except Exception as e:
                    # Only log probe errors if status changed
                    if last_status is not False:
                        _log_monitor(f"Probe Error: {e}")
            else:
                success = False

            # Update shared status
            shared_status.value = 1 if success else 0

            # Log on status change ONLY
            if success != last_status:
                status_str = "Connected" if success else "Disconnected"
                _log_monitor(f"Status Changed: {status_str}")
                last_status = success

            # Sleep with sensitivity to running_event
            for _ in range(50): # 5 seconds total
                if not running_event.is_set():
                    break
                time.sleep(0.1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            _log_monitor(f"Monitor process critical error: {e}")
            time.sleep(5)

class ResolveClient:
    def __init__(self):
        self.resolve = None
        self._lock = threading.Lock()

        # Multiprocessing setup
        self._shared_status = multiprocessing.Value('i', 0)
        self._running_event = multiprocessing.Event()
        self._running_event.set()

        self._proc = multiprocessing.Process(
            target=monitor_resolve_process,
            args=(self._shared_status, self._running_event),
            daemon=True
        )
        self._proc.start()

    def shutdown(self):
        """Cleanly shutdown the monitor process."""
        if hasattr(self, '_proc') and self._proc.is_alive():
            print("[Resolve] Stopping monitor process...")
            self._running_event.clear()

            self._proc.join(timeout=3.0)

            if self._proc.is_alive():
                print("[Resolve] Monitor process did not stop, terminating...")
                self._proc.terminate()
                self._proc.join(timeout=1.0)

            if self._proc.is_alive():
                print("[Resolve] Monitor process still alive, killing...")
                try:
                    import signal
                    os.kill(self._proc.pid, signal.SIGTERM)
                except:
                    pass

    def is_available(self):
        """Instant check via shared memory."""
        return bool(self._shared_status.value)

    def _ensure_connected(self):
        """Try to connect in the MAIN process if available."""
        if self.resolve:
            return True

        try:
             import DaVinciResolveScript as dvr_script
             self.resolve = dvr_script.scriptapp("Resolve")
        except ImportError:
            # Try path add
            path = get_resolve_module_path()

            if path and path not in sys.path:
                 sys.path.append(path)
            try:
                import DaVinciResolveScript as dvr_script
                self.resolve = dvr_script.scriptapp("Resolve")
            except:
                pass

        return self.resolve is not None

    def _log(self, message):
        """Log to a file."""
        try:
            with open(RESOLVE_CLIENT_LOG, "a", encoding="utf-8") as f:
                dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{dt}] {message}\n")
        except Exception:
            print(message)

    def _timecode_to_frames(self, timecode, fps_str):
        """Convert HH:MM:SS:FF timecode to frame count."""
        try:
            # Handle Drop Frame semicolons
            timecode = timecode.replace(';', ':')
            fps = normalize_fps(fps_str)

            parts = timecode.split(':')
            if len(parts) != 4:
                self._log(f"Invalid timecode format: {timecode}")
                return 0

            h, m, s, f = map(int, parts)
            total_frames = (h * 3600 + m * 60 + s) * fps + f
            return total_frames
        except Exception as e:
            self._log(f"Timecode conversion error: {e}")
            return 0

    def _frames_to_timecode(self, total_frames, fps_str):
        """Convert frame count back to HH:MM:SS:FF timecode."""
        try:
            fps = normalize_fps(fps_str)
            if fps == 0: return "00:00:00:00"

            h = total_frames // (3600 * fps)
            m = (total_frames // (60 * fps)) % 60
            s = (total_frames // fps) % 60
            f = total_frames % fps

            return f"{h:02}:{m:02}:{s:02}:{f:02}"
        except Exception as e:
            self._log(f"Frames to timecode conversion error: {e}")
            return "00:00:00:00"

    def _srt_time_to_frames(self, srt_time, fps_str):
        """Convert SRT time string HH:MM:SS,mmm to frame count."""
        try:
            fps = float(fps_str) # Keeping float here for precision in calculation
            # "00:00:05,123"
            parts = srt_time.replace(',', ':').split(':')
            h, m, s, ms = map(int, parts)
            total_seconds = h * 3600 + m * 60 + s + (ms / 1000.0)
            return int(round(total_seconds * fps))
        except Exception as e:
            self._log(f"SRT time conversion error: {e}")
            return 0

    def insert_file(self, file_path, text=None):
        """
        Imports the file into the Media Pool and overwrites at the current playhead position.
        """
        self._log(f"Attempting to insert: {file_path}")

        if not self.is_available():
            return False

        with self._lock:
            if not self._ensure_connected():
                self._log("Resolve not connected")
                return False

            try:
                project_manager = self.resolve.GetProjectManager()
                project = project_manager.GetCurrentProject()
                if not project:
                    self._log("No project open")
                    return False

                media_pool = project.GetMediaPool()
                if not media_pool:
                    self._log("Failed to get Media Pool")
                    return False

                # --- 0. Template Management ---
                from app.config import config
                target_bin_name = config.get("resolve.template_bin", "VoiceVox Captions")
                target_clip_name = config.get("resolve.template_name", "DefaultTemplate")

                root_folder = media_pool.GetRootFolder()
                template_item = None
                target_bin = None

                # Step 1: Search for the target bin
                for sub in root_folder.GetSubFolderList():
                    if sub.GetName() == target_bin_name:
                        target_bin = sub
                        break

                # Step 2: Auto-create the bin if missing
                if not target_bin:
                    try:
                        target_bin = media_pool.AddSubFolder(root_folder, target_bin_name)
                        self._log(f"Created Bin: {target_bin_name}")
                    except Exception as e:
                        self._log(f"Failed to create bin: {e}")

                # Step 3: Find template inside the target bin
                if target_bin:
                    clips = target_bin.GetClipList()

                    for clip in clips:
                        c_name = clip.GetClipProperty("Clip Name")
                        if c_name == target_clip_name:
                            template_item = clip
                            break

                    # Priority 2: Any Text+ in that bin (Name-agnostic)
                    if not template_item:
                        for clip in clips:
                            c_type = clip.GetClipProperty("Type")
                            c_path = clip.GetClipProperty("File Path")
                            if c_path == "" and ("Text" in c_type or "Fusion" in c_type):
                                template_item = clip
                                break

                # Step 4: Final fallback - Global recursive search
                if not template_item:
                    def find_template_recursive(folder):
                        for clip in folder.GetClipList():
                            if clip.GetClipProperty("Clip Name") == target_clip_name:
                                return clip
                        for sub in folder.GetSubFolderList():
                            res = find_template_recursive(sub)
                            if res: return res
                        return None
                    template_item = find_template_recursive(root_folder)

                if not template_item:
                    self._log(f"INFO: No template found. Please ensure a Text+ clip is in the Media Pool.")

                # 1. Import Media
                items = media_pool.ImportMedia([file_path])
                if not items or len(items) == 0:
                    self._log(f"Failed to import media: {file_path}")
                    return False

                media_item = items[0]
                frames_prop = media_item.GetClipProperty("Frames")

                # 2. Add to Timeline at Playhead
                timeline = project.GetCurrentTimeline()
                if not timeline:
                    self._log("No timeline open")
                    return False

                fps_str = timeline.GetSetting("timelineFrameRate")
                current_tc = timeline.GetCurrentTimecode()

                # Use class method for TC conversion
                fps = normalize_fps(fps_str)
                playhead_frame = self._timecode_to_frames(current_tc, fps_str)

                # Determine Clip Duration
                duration_frames = 0
                if frames_prop and str(frames_prop).strip():
                    try:
                        duration_frames = int(frames_prop)
                    except ValueError:
                        pass

                if duration_frames <= 0:
                    duration_tc = media_item.GetClipProperty("Duration")
                    duration_frames = self._timecode_to_frames(duration_tc, fps_str)

                # --- Track Management ---
                target_track_video = config.get("resolve.subtitle_track_index", DEFAULT_VIDEO_TRACK)
                target_track_audio = config.get("resolve.audio_track_index", DEFAULT_AUDIO_TRACK)

                # Ensure Video Tracks exist
                video_track_count = timeline.GetTrackCount("video")
                while video_track_count < target_track_video:
                    if timeline.AddTrack("video"):
                        video_track_count += 1
                    else:
                        break

                # Ensure Audio Tracks exist
                audio_track_count = timeline.GetTrackCount("audio")
                while audio_track_count < target_track_audio:
                    if timeline.AddTrack("audio"):
                        audio_track_count += 1
                    else:
                        break

                # A. Insert Audio
                media_pool.AppendToTimeline([{
                    "mediaPoolItem": media_item,
                    "startFrame": 0,
                    "endFrame": duration_frames,
                    "recordFrame": playhead_frame,
                    "trackIndex": target_track_audio,
                    "mediaType": 2 # Audio
                }])

                # B. Insert Template (Text+) if available
                if template_item:
                    appended_items = media_pool.AppendToTimeline([{
                        "mediaPoolItem": template_item,
                        "startFrame": 0,
                        "endFrame": duration_frames,
                        "recordFrame": playhead_frame,
                        "trackIndex": target_track_video,
                        "mediaType": 1 # Video
                    }])

                    if appended_items and len(appended_items) > 0:
                        timeline_item = appended_items[0]
                        if text:
                            self._update_fusion_text(timeline_item, text)

                self._log(f"Inserted media at {current_tc}")
                return True

            except Exception as e:
                self._log(f"Insertion error: {e}")
                self._log(traceback.format_exc())
                return False

    def _update_fusion_text(self, item, text):
        """Helper to update TextPlus content."""
        try:
            time.sleep(0.05)
            comp = item.GetFusionCompByIndex(1)
            if comp:
                tool = comp.FindTool("Template")
                if not tool:
                    tools = comp.GetToolList(False, "TextPlus")
                    if tools:
                        tool = list(tools.values())[0] if isinstance(tools, dict) else tools[0]
                if tool:
                    tool.SetInput("StyledText", text)
                else:
                    self._log("No TextPlus tool found in Fusion comp")
            else:
                self._log("GetFusionCompByIndex(1) returned None")
        except Exception as e:
            self._log(f"Fusion update error: {e}")
