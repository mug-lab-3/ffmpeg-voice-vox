import os
import sys
import ctypes
import shutil
import urllib.request
import zipfile
import threading
import subprocess
from pathlib import Path

# Global list to keep DLL directory handles alive using os.add_dll_directory
_DLL_HANDLES = []

def check_and_setup():
    manager = DependencyManager()
    manager.setup_environment()

class DependencyManager:
    """
    Manages runtime dependencies, specifically CUDA/cuDNN libraries for portable GPU support.
    """
    def __init__(self, tools_dir="tools"):
        self.base_dir = Path.cwd()
        self.tools_dir = self.base_dir / tools_dir
        self.cudnn_dir = self.tools_dir / "cudnn"
        # Updated URL for CUDA 12 libs (matching CTranslate2 4.x/cuDNN 9)
        # Using the v3 release which contains cuDNN 9.8 and cuBLAS 12
        self.libs_url = "https://github.com/Purfview/whisper-standalone-win/releases/download/libs/cuBLAS.and.cuDNN_CUDA12_win_v3.7z"
        self.lock = threading.Lock()

    def has_nvidia_gpu(self) -> bool:
        """
        Checks for NVIDIA GPU presence using simple DLL detection or nvml.
        Using ctypes to check for nvcuda.dll is a lightweight method.
        """
        try:
            # Check if nvcuda.dll exists in system (Driver installed)
            ctypes.CDLL("nvcuda.dll")
            return True
        except (OSError, FileNotFoundError):
            return False

    def are_libraries_present(self) -> bool:
        """Checks if the portable libraries are already installed."""
        # Check for key DLLs. CTranslate2 4.x usually needs cublas64_12.dll for CUDA 12.
        # We checked installed package and it has cudnn64_9.dll, implying CUDA 12.
        required_dlls = ["cublas64_12.dll"] 
        
        bin_dir = self.cudnn_dir / "bin"
        if not bin_dir.exists():
            # Sometimes they might be in root of cudnn_dir depending on extraction
            bin_dir = self.cudnn_dir
            
        for dll in required_dlls:
            if not (bin_dir / dll).exists():
                return False
        return True

    def download_and_extract(self):
        """Downloads and extracts the runtime libraries."""
        if self.are_libraries_present():
            return

        print("[Dependencies] NVIDIA GPU detected. Downloading runtime libraries for acceleration...")
        print(f"[Dependencies] Downloading from {self.libs_url}")
        
        # Determine filename from URL
        filename = self.libs_url.split("/")[-1]
        archive_path = self.tools_dir / filename
        self.cudnn_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            print(f"[Dependencies] Downloading with curl: {self.libs_url}")
            # Use curl for faster/resumable download. 
            # -L follows redirects, -C - resumes, -o sets output
            cmd = ["curl", "-L", "-C", "-", "-o", str(archive_path), self.libs_url]
            
            # Show progress in standard output
            subprocess.run(cmd, check=True)
            
            print("[Dependencies] Extracting libraries (using tar)...")
            
            # Use tar to extract .7z (Windows 10/11 tar supports it or we rely on system capability)
            # -C specifies directory
            try:
                subprocess.run(["tar", "-xf", str(archive_path), "-C", str(self.cudnn_dir)], check=True)
            except subprocess.CalledProcessError as e:
                print(f"[Dependencies] Tar extraction failed: {e}")
                raise
            except FileNotFoundError:
                 print("[Dependencies] 'tar' command not found. Cannot extract .7z.")
                 raise

            # Re-organize if needed. Purfview libs usually flatten or have specific structure.
            # We look for .dlls and ensure they are in a 'bin' folder or added to path.
            dlls = list(self.cudnn_dir.rglob("*.dll"))
            if dlls:
                bin_dir = self.cudnn_dir / "bin"
                bin_dir.mkdir(exist_ok=True)
                for dll in dlls:
                    # Move to bin if not already there
                    if dll.parent != bin_dir:
                        shutil.move(str(dll), str(bin_dir / dll.name))
                    
            print("[Dependencies] Runtime libraries installed successfully.")
            
        except Exception as e:
            print(f"[Dependencies] Failed to download/install libraries: {e}")
            if archive_path.exists():
                os.remove(archive_path)
            raise
        finally:
            if archive_path.exists():
                os.remove(archive_path)

    def check_ctranslate2_working(self) -> bool:
        """
        New smart check: Runs a small subprocess to see if CTranslate2 can load CUDA.
        This handles cases where wheels are self-contained or system libs are sufficient.
        """
        try:
            # We use an inline script or existing script to check
            cmd = [
                sys.executable, 
                "-c", 
                "import ctranslate2; count = ctranslate2.get_cuda_device_count(); print(f'Devices: {count}')"
            ]
            # Capture output
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_dir)
            if result.returncode == 0 and "Devices:" in result.stdout:
                # Must actually find > 0 devices
                if "Devices: 0" in result.stdout:
                    return False
                print(f"[Dependencies] CTranslate2 validation passed: {result.stdout.strip()}")
                return True
            else:
                # print(f"[Dependencies] CTranslate2 validation failed or no GPU found: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"[Dependencies] Validation subprocess error: {e}")
            return False

    def setup_environment(self):
        """
        Adds the library path to os.environ['PATH'] so CTranslate2 can find them.
        MUST be called before importing faster_whisper/ctranslate2.
        """
        # 1. Preliminary Check: Do we even have an NVIDIA GPU?
        if not self.has_nvidia_gpu():
            print("[Dependencies] No NVIDIA GPU detected (via nvcuda.dll detection). Skipping library setup.")
            return

        # 2. Prioritize Local Libs: If we have them, ADD THEM FIRST.
        # This addresses the issue where get_cuda_device_count() works (driver ok) but cublas is missing.
        bin_dir = self.cudnn_dir / "bin"
        if not bin_dir.exists() and (self.cudnn_dir / "cublas64_12.dll").exists():
            bin_dir = self.cudnn_dir

        if bin_dir.exists():
             print(f"[Dependencies] Local libs found at {bin_dir}. Adding to PATH/DLL search.")
             self._add_to_path(bin_dir)

        # 3. Smart Check: Does it work now?
        if self.check_ctranslate2_working():
             print("[Dependencies] CUDA validation passed. Libraries are accessible.")
             return

        # 4. If not working, Download.
        print("[Dependencies] CUDA not working. Attempting to download runtime libraries...")

        if bin_dir.exists():
             print(f"[Dependencies] Local libs found at {bin_dir}. Adding to PATH/DLL search.")
             self._add_to_path(bin_dir)
             
             # Re-check
             if self.check_ctranslate2_working():
                 print("[Dependencies] CUDA working with local libs.")
                 return
        
        # C. Download
        print("[Dependencies] CUDA not working. Attempting to download runtime libraries...")
        try:
            self.download_and_extract()
            # bin_dir might have been created
            bin_dir = self.cudnn_dir / "bin"
            if not bin_dir.exists() and (self.cudnn_dir / "cublas64_12.dll").exists():
                bin_dir = self.cudnn_dir
                
            if bin_dir.exists():
                self._add_to_path(bin_dir)
        except Exception as e:
            print(f"[Dependencies] WARN: Could not setup GPU libraries. Will fall back to CPU. ({e})")
            return

        # Final check
        if self.check_ctranslate2_working():
            print("[Dependencies] Setup successful! CUDA enabled.")
        else:
            print("[Dependencies] WARN: CUDA setup attempted but verification failed. Fallback to CPU likely.")

    def _add_to_path(self, path: Path):
        """Helper to safely add to PATH and DLL search path."""
        path_str = str(path)
        if path_str not in os.environ["PATH"]:
            os.environ["PATH"] = path_str + os.pathsep + os.environ["PATH"]
        
        if hasattr(os, 'add_dll_directory'):
            try:
                # IMPORTANT: We must keep the handle alive!
                handle = os.add_dll_directory(path_str)
                _DLL_HANDLES.append(handle)
                # print(f"[Dependencies] Added DLL directory: {path_str}")
            except Exception as e:
                print(f"[Dependencies] Failed to add DLL directory: {e}")
                
        # PRELOAD DLLs: Explicitly load key DLLs to ensure they are in memory.
        # This works around search path issues often encountered with CTranslate2/Whisper on Windows.
        try:
            for dll in path.glob("*.dll"):
                # We mainly care about cublas/cudnn, but loading all helps resolve inter-dependencies (like ops dependent on main cudnn)
                # Load with default flags (which now include the directory we just added via add_dll_directory)
                try:
                    ctypes.CDLL(str(dll))
                    # print(f"[Dependencies] Preloaded {dll.name}")
                except Exception:
                    pass # Ignore load failures for non-critical/dependency-order issues
            print(f"[Dependencies] Preloaded libraries from {path.name}")
        except Exception as e:
            print(f"[Dependencies] Warning during DLL preload: {e}")
