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
                self._log(f"Timeline FPS: {fps_str}, TC: {current_tc}")
                
                # Calculate absolute frames for recordFrame (Target Position)
                record_frame = self._timecode_to_frames(current_tc, fps_str)
                self._log(f"Calculated Record Frame: {record_frame}")
                
                # Determine Clip Duration in frames
                # 'Frames' property might be empty for some audio files
                frames_prop = media_item.GetClipProperty("Frames")
                duration_frames = 0
                
                if frames_prop and str(frames_prop).strip():
                    try:
                        duration_frames = int(frames_prop)
                    except ValueError:
                        pass
                
                if duration_frames == 0:
                    # Fallback to Duration timecode
                    duration_tc = media_item.GetClipProperty("Duration")
                    self._log(f"Frames property empty, using Duration TC: {duration_tc}")
                    # Use timeline FPS for audio frame count calculation (audio is frame-agnostic but aligned to timeline)
                    duration_frames = self._timecode_to_frames(duration_tc, fps_str)
                    
                self._log(f"Final Clip Duration Frames: {duration_frames}")

                if duration_frames <= 0:
                     self._log("Failed to determine clip duration")
                     return False
                
                # From app config
                from app.config import config
                track_index = config.get("resolve.track_index", 1) 
                
                # Construct Clip Info definition
                clip_info = {
                    "mediaPoolItem": media_item,
                    "startFrame": 0,
                    "endFrame": duration_frames - 1,
                    "trackIndex": track_index,
                    "recordFrame": record_frame,
                    "mediaType": 2 # 1=Video, 2=Audio
                }
                self._log(f"Clip Info: {clip_info}")

                # Note: AppendToTimeline signature checks
                # If this method signature is [clipInfo] (list of dicts)
                appended = media_pool.AppendToTimeline([clip_info])
                
                # Since AppendToTimeline returns list of appended items, empty list means failure
                if appended and len(appended) > 0:
                    self._log(f"Success. Appended: {appended}")
                    return True
                else:
                    self._log("AppendToTimeline returned failure (empty list or None)")
                    return False

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self._log(f"Exception during insertion: {e}\n{tb}")
                return False

 

