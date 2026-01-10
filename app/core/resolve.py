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
    while running_event.is_set():
        success = False
        try:
            # Try to load and connect
            # We must duplicate the load logic here or import it 
            # But simple is better for a process
            dvr_script = None
            
            # 1. Try existing import
            try:
                import DaVinciResolveScript as dvr
                dvr_script = dvr
            except ImportError:
                # 2. Try manual path loading (Windows logic primarily)
                if platform.system() == "Windows":
                    expected_path = os.path.join(os.getenv('PROGRAMDATA', ''), 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules')
                    if os.path.exists(expected_path) and expected_path not in sys.path:
                        sys.path.append(expected_path)
                
                try:
                    import DaVinciResolveScript as dvr
                    dvr_script = dvr
                except ImportError:
                    pass

            if dvr_script:
                # The heavy blocking call
                resolve = dvr_script.scriptapp("Resolve")
                if resolve:
                    success = True
        except Exception:
            pass

        # Update shared status
        shared_status.value = 1 if success else 0

        # Backoff logic
        # If success, check every 5s to detect crash quickly
        # If fail, backoff to avoid spamming the checking mechanism
        if success:
            time.sleep(5)
        else:
            # If not found, sleep longer (15s) to reduce CPU/GIL usage impact even in separate process?
            # Actually separate process doesn't affect Main GIL. 
            time.sleep(15) 

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

    def insert_file(self, file_path):
        if not self.is_available():
            return False
            
        with self._lock:
            if not self._ensure_connected():
                return False
                
            try:
                project_manager = self.resolve.GetProjectManager()
                project = project_manager.GetCurrentProject()
                if not project: return False
                
                mediapool = project.GetMediaPool()
                folder = mediapool.GetCurrentFolder()
                
                # Import
                items = mediapool.ImportMedia([file_path])
                if not items: return False
                
                # Append to timeline (simplified)
                timeline = project.GetCurrentTimeline()
                if not timeline:
                    # Create one? Or just add to pool?
                    # User request implies "Insert". 
                    # If no timeline, maybe just pool is enough.
                    pass
                else:
                    timeline.AppendToTimeline(items)
                
                return True
            except Exception as e:
                print(f"[Resolve] Insert Error: {e}")
                self.resolve = None # Reset connection
                return False

# Global instance
resolve_client = ResolveClient() 
        
        # The actual insert logic is large, so I need to preserve it.
        # But wait, insert_file in original code calls _load_module if not resolve.
        # Here we should rely on background thread OR try simple check?
        # If user clicks Insert, we want immediate attempt?
        # But for 'status' check, we want non-blocking.
        
        # Ideally, insert_file should be blocking/direct because user requested action.
        # But is_available (status check) should be non-blocking.
        
        return self._do_insert(file_path)

    def _do_insert(self, file_path):
        # ... logic from original insert_file ...
        # I cannot replace the whole file easily with replace_file_content if I change structure too much.
        # I will keep the original structure but update __init__ and is_available.
        # And remove the 'retry' logic from is_available.
        pass


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
        
        if not self.resolve:
            self._load_module()
            if not self.resolve:
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
