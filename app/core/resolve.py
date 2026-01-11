import sys
import os
import platform
import threading
import time
import multiprocessing
import importlib

# Standalone function for the separate process
def monitor_resolve_process(shared_status, running_event):
    """
    Runs in a separate process.
    Continuously checks if DaVinci Resolve is reachable.
    Updates shared_status (0=No, 1=Yes).
    """
    import sys
    import time
    import importlib
    import os
    import platform

    # Setup local logger for this process
    def log(msg):
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            log_file = os.path.join(log_dir, "resolve_monitor.log")
            
            with open(log_file, "a", encoding="utf-8") as f:
                import datetime
                dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{dt}] {msg}\n")
        except:
            pass

    log("Monitor process started")

    last_status = None # None indicates startup/unknown
    dvr_module = None

    while running_event.is_set():
        try:
            success = False
            
            # STEP 0: Check if Resolve process even exists before doing heavy API calls
            is_running = False
            import subprocess
            try:
                if platform.system() == "Windows":
                    # Using tasklist is faster and lighter than scripting API probes
                    cmd = 'tasklist /FI "IMAGENAME eq Resolve.exe" /NH'
                    out = subprocess.check_output(cmd, shell=True, creationflags=0x08000000).decode('cp932', errors='ignore')
                    if "Resolve.exe" in out:
                        is_running = True
                else:
                    is_running = True # Fallback for other OS
            except:
                is_running = True # If command fails, fall back to probe

            if is_running:
                try:
                    # Setup path just in case (only once)
                    if platform.system() == "Windows":
                        expected_path = os.path.join(os.getenv('PROGRAMDATA', ''), 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules')
                        if os.path.exists(expected_path) and expected_path not in sys.path:
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
                        log(f"Probe Error: {e}")
            else:
                # Resolve is not even in task list, definitely not success
                success = False

            # Update shared status
            shared_status.value = 1 if success else 0
            
            # Log on status change ONLY
            if success != last_status:
                status_str = "Connected" if success else "Disconnected"
                log(f"Status Changed: {status_str}")
                last_status = success

            # Sleep with more sensitivity to running_event
            for _ in range(50): # 5 seconds total, but check every 0.1s
                if not running_event.is_set():
                    break
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Monitor process critical error: {e}")
            time.sleep(5)

class ResolveClient:
    def __init__(self):
        self.resolve = None
        self.script_module = None
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
            
            # Wait for clean exit
            self._proc.join(timeout=3.0)
            
            if self._proc.is_alive():
                print("[Resolve] Monitor process did not stop, terminating...")
                self._proc.terminate()
                self._proc.join(timeout=1.0)
                
            if self._proc.is_alive():
                print("[Resolve] Monitor process still alive, killing...")
                try:
                    import os
                    import signal
                    os.kill(self._proc.pid, signal.SIGTERM)
                except:
                    pass


    def is_available(self):
        # Instant check via shared memory
        return bool(self._shared_status.value)

    def _ensure_connected(self):
        """Try to connect in the MAIN process if available."""
        if self.resolve:
            return True
            
        # Try to load (Main process version)
        try:
             import DaVinciResolveScript as dvr_script
             self.resolve = dvr_script.scriptapp("Resolve")
        except ImportError:
            # Try path add
            if platform.system() == "Windows":
                path = os.path.join(os.getenv('PROGRAMDATA', ''), 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules')
                if path not in sys.path:
                     sys.path.append(path)
            try:
                import DaVinciResolveScript as dvr_script
                self.resolve = dvr_script.scriptapp("Resolve")
            except:
                pass
                
        return self.resolve is not None

    def _log(self, message):
        """Log to a file since console might be hidden/inaccessible."""
        try:
            with open("resolve.log", "a", encoding="utf-8") as f:
                timestamp = os.path.getmtime("resolve.log") if os.path.exists("resolve.log") else 0
                import datetime
                dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{dt}] {message}\n")
        except Exception:
            print(message)

    def _timecode_to_frames(self, timecode, fps_str):
        """Convert HH:MM:SS:FF timecode to frame count."""
        try:
            # Handle Drop Frame semicolons
            timecode = timecode.replace(';', ':')
            
            fps = float(fps_str)
            # Rounding logic
            if 29.0 < fps < 30.0: fps = 30 
            elif 59.0 < fps < 60.0: fps = 60 
            elif 23.0 < fps < 24.0: fps = 24 
            
            fps = int(round(fps))
            
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
            fps = float(fps_str)
            if 29.0 < fps < 30.0: fps = 30 
            elif 59.0 < fps < 60.0: fps = 60 
            elif 23.0 < fps < 24.0: fps = 24 
            fps = int(round(fps))
            
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
            fps = float(fps_str)
            # "00:00:05,123"
            parts = srt_time.replace(',', ':').split(':')
            h, m, s, ms = map(int, parts)
            total_seconds = h * 3600 + m * 60 + s + (ms / 1000.0)
            return int(round(total_seconds * fps))
        except Exception as e:
            self._log(f"SRT time conversion error: {e}")
            return 0

    def insert_file(self, file_path):
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

                # --- 0. Template Management (Simplified & Safe) ---
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
                
                # Step 2: Auto-create the bin if missing (SAFE)
                if not target_bin:
                    try:
                        target_bin = media_pool.AddSubFolder(root_folder, target_bin_name)
                        self._log(f"Created Bin: {target_bin_name}")
                    except Exception as e:
                        self._log(f"Failed to create bin: {e}")
                
                # Step 3: Find template inside the target bin
                if target_bin:
                    clips = target_bin.GetClipList()
                    self._log(f"Searching bin '{target_bin_name}' (Clip count: {len(clips)})")
                    
                    for clip in clips:
                        c_name = clip.GetClipProperty("Clip Name")
                        c_type = clip.GetClipProperty("Type")
                        c_path = clip.GetClipProperty("File Path")
                        self._log(f"Checking clip: '{c_name}' (Type: '{c_type}', Path: '{c_path}')")
                        
                        # Priority 1: Specific Name
                        if c_name == target_clip_name:
                            template_item = clip
                            self._log(f"Match found by name: {target_clip_name}")
                            break
                    
                    # Priority 2: Any Text+ in that bin (Name-agnostic)
                    if not template_item:
                        for clip in clips:
                            c_type = clip.GetClipProperty("Type")
                            c_path = clip.GetClipProperty("File Path")
                            # If it's a generator (empty path) and contains 'Text' or is 'Fusion Title'
                            if c_path == "" and ("Text" in c_type or "Fusion" in c_type):
                                template_item = clip
                                self._log(f"Using first compatible Text+ as template: {clip.GetClipProperty('Clip Name')}")
                                break
                
                # Step 4: Final fallback - Global recursive search by name
                if not template_item:
                    self._log(f"Global recursive search for '{target_clip_name}'...")
                    def find_template_recursive(folder):
                        for clip in folder.GetClipList():
                            if clip.GetClipProperty("Clip Name") == target_clip_name:
                                return clip
                        for sub in folder.GetSubFolderList():
                            res = find_template_recursive(sub)
                            if res: return res
                        return None
                    template_item = find_template_recursive(root_folder)
                    if template_item:
                        self._log(f"Global match found: {template_item.GetClipProperty('Clip Name')}")

                if not template_item:
                    self._log(f"INFO: No template found in '{target_bin_name}' or globally. Please ensure a Text+ clip is in the Media Pool.")

                # 1. Import Media
                items = media_pool.ImportMedia([file_path])
                if not items or len(items) == 0:
                    self._log(f"Failed to import media: {file_path}")
                    return False
                
                media_item = items[0]
                frames_prop = media_item.GetClipProperty("Frames")
                self._log(f"Imported Media Frames: {frames_prop}")

                # 2. Add to Timeline at Playhead
                timeline = project.GetCurrentTimeline()
                if not timeline:
                    self._log("No timeline open")
                    return False

                # Get settings for position calculation
                fps_str = timeline.GetSetting("timelineFrameRate")
                current_tc = timeline.GetCurrentTimecode()

                # Conversion Logic: Timecode -> Frame Number
                def tc_to_frames(tc, fps):
                    parts = list(map(int, tc.split(':')))
                    return ((parts[0] * 3600 + parts[1] * 60 + parts[2]) * fps) + parts[3]

                fps = float(fps_str)
                playhead_frame = tc_to_frames(current_tc, fps)
                duration_frames = int(frames_prop) if frames_prop else 0

                # --- Track Management (Restored) ---
                from app.config import config
                target_track_video = config.get("resolve.subtitle_track_index", 2)
                target_track_audio = config.get("resolve.audio_track_index", 1)

                # Ensure Video Tracks exist
                video_track_count = timeline.GetTrackCount("video")
                while video_track_count < target_track_video:
                    if timeline.AddTrack("video"):
                        video_track_count += 1
                        self._log(f"Added video track. New count: {video_track_count}")
                    else:
                        break

                # Ensure Audio Tracks exist
                audio_track_count = timeline.GetTrackCount("audio")
                while audio_track_count < target_track_audio:
                    if timeline.AddTrack("audio"):
                        audio_track_count += 1
                        self._log(f"Added audio track. New count: {audio_track_count}")
                    else:
                        break

                # A. Insert Audio
                media_pool.AppendToTimeline([{
                    "mediaPoolItem": media_item,
                    "startFrame": 0,
                    "endFrame": duration_frames,
                    "recordFrame": playhead_frame,
                    "trackIndex": target_track_audio,
                    "mediaType": 2 # 2=Audio
                }])

                # B. Insert Template (Text+) if available
                if template_item:
                    # Append Text+ clip at Video Track
                    appended_items = media_pool.AppendToTimeline([{
                        "mediaPoolItem": template_item,
                        "startFrame": 0,
                        "endFrame": duration_frames,
                        "recordFrame": playhead_frame,
                        "trackIndex": target_track_video,
                        "mediaType": 1 # 1=Video
                    }])
                    
                    if appended_items and len(appended_items) > 0:
                        timeline_item = appended_items[0]
                        # Injection: Direct Text -> Fusion Text+
                        if text:
                            self._log(f"Injecting text into Text+: {text}")
                            # In Fusion Text+, the main text parameter is 'StyledText'
                            timeline_item.SetSetting("StyledText", text)

                self._log(f"Inserted media at {current_tc} on video track {target_track_video}")
                return True

            except Exception as e:
                self._log(f"Insertion error: {e}")
                import traceback
                self._log(traceback.format_exc())
                return False

    def _update_fusion_text(self, item, text):
        """Helper to update TextPlus content."""
        def update_task():
            try:
                # Brief wait to ensure Resolve has initialized the Fusion comp for the new item
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
        
        # We can run this in a small thread if needed, but sequential is safer for now
        update_task()

    def _insert_sequential(self, timeline, texts, clip_infos, fps_str):
        # (This method is now effectively deprecated by mandatory template rule)
        pass
