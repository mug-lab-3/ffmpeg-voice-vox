import sys
import os
import platform

class ResolveClient:
    def __init__(self):
        self.resolve = None
        self.script_module = None
        self._load_module()

    def _load_module(self):
        """Load the DaVinci Resolve script module dynamically with env support."""
        try:
            # Check for existing module (e.g. running inside Resolve Console)
            try:
                import DaVinciResolveScript as dvr_script
                self.script_module = dvr_script
                self.resolve = dvr_script.scriptapp("Resolve")
                if self.resolve:
                    return
            except ImportError:
                pass

            # Determine path based on OS
            system = platform.system()
            lib_path = ""
            
            if system == "Windows":
                program_data = os.getenv('PROGRAMDATA')
                if program_data:
                    lib_path = os.path.join(program_data, 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules')
            elif system == "Darwin": # Mac
                lib_path = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
            elif system == "Linux":
                lib_path = "/opt/resolve/Developer/Scripting/Modules"

            if lib_path and os.path.exists(lib_path):
                if lib_path not in sys.path:
                    sys.path.append(lib_path)
                
                try:
                    import DaVinciResolveScript as dvr_script
                    self.script_module = dvr_script
                    self.resolve = dvr_script.scriptapp("Resolve")
                except ImportError as e:
                     print(f"[Resolve] Failed to import module from {lib_path}: {e}")
            else:
                 print(f"[Resolve] Module path not found: {lib_path}")

        except Exception as e:
            print(f"[Resolve] Failed to initialize: {e}")

    def is_available(self):
        return self.resolve is not None

    def insert_file(self, file_path):
        """
        Imports the file into the Media Pool and appends it to the current Timeline.
        """
        if not self.resolve:
            # Try reloading just in case it wasn't running before
            self._load_module()
            if not self.resolve:
                print("[Resolve] Not connected")
                return False

        try:
            project_manager = self.resolve.GetProjectManager()
            project = project_manager.GetCurrentProject()
            if not project:
                print("[Resolve] No project open")
                return False

            media_pool = project.GetMediaPool()
            if not media_pool:
                print("[Resolve] Failed to get Media Pool")
                return False

            # 1. Import Media
            # ImportMedia accepts a list of paths
            items = media_pool.ImportMedia([file_path])
            if not items or len(items) == 0:
                print(f"[Resolve] Failed to import media: {file_path}")
                return False
            
            clip = items[0]

            # 2. Add to Timeline
            # Note: AppendToTimeline adds to the end.
            # Usually creates a timeline if none exists? No, must exist.
            timeline = project.GetCurrentTimeline()
            if not timeline:
                print("[Resolve] No timeline open")
                return False

            # mediaPool.AppendToTimeline(clips) returns [TimelineItem]
            # This appends to the target track (usually the end of it).
            # There isn't a simple "Insert at Playhead" in the basic v1 API.
            # We will use AppendToTimeline for now as it's the standard API.
            appended = media_pool.AppendToTimeline([clip])
            
            if appended:
                print(f"[Resolve] Imported and appended: {file_path}")
                return True
            else:
                print("[Resolve] Failed to append to timeline")
                return False

        except Exception as e:
            print(f"[Resolve] Error during insertion: {e}")
            return False
