import os
import sys
import ctypes
from pathlib import Path

# Path to our downloaded bin
dll_dir = Path(r"c:\Users\mug\OneDrive\Desktop\ffmpeg-voice-vox\tools\cudnn\bin")

print(f"Target Dir: {dll_dir}")
print(f"Exists: {dll_dir.exists()}")

if dll_dir.exists():
    # 1. Add to PATH
    os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ["PATH"]
    
    # 2. Add DLL Directory
    try:
        handle = os.add_dll_directory(str(dll_dir))
        print("os.add_dll_directory successful")
    except Exception as e:
        print(f"os.add_dll_directory failed: {e}")

    # 3. Try loading libraries one by one
    libs = [
        "cublasLt64_12.dll", # Often a dependency of cublas
        "cublas64_12.dll",
        "cudnn_ops64_9.dll",
        "cudnn64_9.dll"
    ]

    for lib in libs:
        path = dll_dir / lib
        print(f"--- Loading {lib} ---")
        if not path.exists():
            print("  -> File not found!")
            continue
            
        try:
            # Use LoadLibraryEx with LOAD_WITH_ALTERED_SEARCH_PATH behavior via basic CDLL
            # WinError 126 = Module not found (dependencies missing)
            # WinError 193 = Bad Image (arch mismatch)
            ctypes.CDLL(str(path))
            print("  -> Success!")
        except OSError as e:
            print(f"  -> Failed: {e}")
            if hasattr(e, 'winerror'):
                print(f"  -> WinError: {e.winerror}")
                if e.winerror == 126:
                    print("     (Module not found - likely missing dependency like zlibwapi.dll or MSVC runtime)")
                elif e.winerror == 193:
                    print("     (Bad Image - likely 32/64 bit mismatch)")
else:
    print("DLL Directory not found.")
