import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import pytest

from app.core.resolve import (
    get_resolve_module_path,
    normalize_fps,
    ResolveClient
)

class TestResolveCore:

    @pytest.mark.parametrize("input_fps,expected", [
        (23.976, 24),
        (24.0, 24),
        (29.97, 30),
        (30.0, 30),
        (59.94, 60),
        (60.0, 60),
        ("29.97", 30),
        (25, 25),
        ("invalid", 0),
        (None, 0)
    ])
    def test_normalize_fps(self, input_fps, expected):
        """Test FPS normalization logic."""
        assert normalize_fps(input_fps) == expected

    def test_get_resolve_module_path_windows(self):
        """Test path resolution on Windows."""
        with patch("platform.system", return_value="Windows"):
             with patch.dict(os.environ, {"PROGRAMDATA": "C:\\ProgramData"}):
                path = get_resolve_module_path()
                expected = "C:\\ProgramData\\Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules"
                # Normalize slashes for comparison if needed, but the code uses join which might use backslash
                # The code: os.path.join(..., 'Blackmagic ...')
                # On Windows mock, path.join will use backslash if we mock os.path too, but real os.path depends on runner.
                # Assuming test runs on Windows or we check endswith
                assert "Blackmagic Design" in path
                assert "Scripting" in path

    def test_get_resolve_module_path_mac(self):
        """Test path resolution on Mac."""
        with patch("platform.system", return_value="Darwin"):
            path = get_resolve_module_path()
            assert path == "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"

    def test_get_resolve_module_path_linux(self):
        """Test path resolution on Linux/Unknown."""
        with patch("platform.system", return_value="Linux"):
            path = get_resolve_module_path()
            assert path is None

    @patch("app.core.resolve.multiprocessing.Process")
    def test_resolve_client_init(self, mock_process):
        """Test ResolveClient initialization starts monitor process."""
        client = ResolveClient()
        mock_process.assert_called_once()
        assert client._proc.start.called

    @patch("app.core.resolve.multiprocessing.Process")
    def test_timecode_to_frames(self, mock_process):
        """Test timecode conversion logic inside Client."""
        client = ResolveClient()
        # 01:00:00:00 at 24fps -> 3600 * 24 = 86400 frames
        frames = client._timecode_to_frames("01:00:00:00", 24)
        assert frames == 86400

        # 00:00:01:12 at 30fps -> 30 + 12 = 42 frames
        frames = client._timecode_to_frames("00:00:01:12", 29.97)
        assert frames == 42 # 29.97 -> 30

    @patch("app.core.resolve.multiprocessing.Process")
    def test_frames_to_timecode(self, mock_process):
        """Test frames to timecode conversion."""
        client = ResolveClient()
        # 86400 frames at 24fps -> 01:00:00:00
        tc = client._frames_to_timecode(86400, 24)
        assert tc == "01:00:00:00"

        # 42 frames at 30fps -> 00:00:01:12
        tc = client._frames_to_timecode(42, 29.97)
        assert tc == "00:00:01:12"

    @patch("app.core.resolve.multiprocessing.Process")
    def test_srt_time_to_frames(self, mock_process):
        """Test SRT timestamp conversion."""
        client = ResolveClient()
        # 00:00:01,500 at 30fps -> 1.5s * 30 = 45 frames
        frames = client._srt_time_to_frames("00:00:01,500", "30")
        assert frames == 45

class TestMonitorProcess:
    @patch("app.core.resolve.time.sleep") # Prevent slow tests
    @patch("app.core.resolve._log_monitor")
    @patch("app.core.resolve.get_resolve_module_path")
    def test_monitor_loop(self, mock_path, mock_log, mock_sleep):
        """Test the monitor process loop updates shared status."""
        from app.core.resolve import monitor_resolve_process

        # Setup mocks
        shared_status = MagicMock()
        running_event = MagicMock()
        # Ensure enough values: Start Loop -> Check in sleep loop (False breaks it) -> Check While (False breaks it)
        running_event.is_set.side_effect = [True, False, False, False]

        # Mock process iteration finding "Resolve"
        mock_proc = MagicMock()
        mock_proc.info = {'name': 'DaVinci Resolve'}

        # Mock psutil module
        mock_psutil_mod = MagicMock()
        mock_psutil_mod.process_iter.return_value = [mock_proc]
        mock_psutil_mod.NoSuchProcess = Exception
        mock_psutil_mod.AccessDenied = Exception
        mock_psutil_mod.ZombieProcess = Exception

        mock_path.return_value = "C:/Path"

        # Mock Resolve API import and connection
        mock_dvr = MagicMock()
        mock_resolve = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        # Patch both psutil and DaVinciResolveScript
        with patch.dict(sys.modules, {
            'DaVinciResolveScript': mock_dvr,
            'psutil': mock_psutil_mod
        }):
            monitor_resolve_process(shared_status, running_event)

        # Verify status was updated to 1 because resolve was found and scriptapp returned object
        assert shared_status.value == 1

class TestResolveClientLifecycle:
    @patch("app.core.resolve.multiprocessing.Process")
    def test_shutdown(self, mock_proc_cls):
        """Test shutdown logic."""
        client = ResolveClient()
        mock_proc = client._proc # Mock process object
        # Initial check -> join -> check -> terminate -> check -> kill
        # Should provide enough False
        mock_proc.is_alive.side_effect = [True, False, False, False, False]

        client.shutdown()

        assert client._running_event.is_set() is False # Should include clear()
        mock_proc.join.assert_called()

    @patch("app.core.resolve.multiprocessing.Process")
    def test_init(self, mock_proc_cls):
        client = ResolveClient()
        assert client.resolve is None
        mock_proc_cls.assert_called()
        client._proc.start.assert_called()

    # Add failure coverage for monitor
    @patch("app.core.resolve.time.sleep")
    @patch("app.core.resolve._log_monitor")
    @patch("app.core.resolve.get_resolve_module_path")
    def test_monitor_failures(self, mock_path, mock_log, mock_sleep):
        from app.core.resolve import monitor_resolve_process

        # 1. psutil ImportError
        with patch.dict(sys.modules, {'psutil': None}): # removes psutil
            shared = MagicMock()
            stop_evt = MagicMock()
            stop_evt.is_set.side_effect = [True, False, False]

            # If psutil import fails, it sets is_running=True (fallback)
            # Then tries to import DaVinciResolveScript -> fails -> success=False
            monitor_resolve_process(shared, stop_evt)
            assert shared.value == 0

        # 2. Resolve Import Error
        mock_psutil = MagicMock()
        mock_proc = MagicMock()
        mock_proc.info = {'name': 'Resolve'}
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch.dict(sys.modules, {'psutil': mock_psutil, 'DaVinciResolveScript': None}):
            shared = MagicMock()
            stop_evt = MagicMock()
            stop_evt.is_set.side_effect = [True, False, False]

            monitor_resolve_process(shared, stop_evt)
            assert shared.value == 0


class TestResolveInsertion:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        # Config mock
        self.patcher_config = patch("app.config.config")
        self.mock_config = self.patcher_config.start()
        # Set defaults similar to what we expect
        self.mock_config.get.side_effect = lambda key, default=None: default

        # Prevent Process spawning
        self.patcher_process = patch("app.core.resolve.multiprocessing.Process")
        self.mock_process_cls = self.patcher_process.start()

        # Resolve mocks
        self.mock_resolve = MagicMock()
        self.mock_project_manager = MagicMock()
        self.mock_project = MagicMock()
        self.mock_media_pool = MagicMock()
        self.mock_timeline = MagicMock()

        # Chain them
        self.mock_resolve.GetProjectManager.return_value = self.mock_project_manager
        self.mock_project_manager.GetCurrentProject.return_value = self.mock_project
        self.mock_project.GetMediaPool.return_value = self.mock_media_pool
        self.mock_project.GetCurrentTimeline.return_value = self.mock_timeline

        # Setup standard returns
        self.mock_timeline.GetSetting.return_value = "30"
        self.mock_timeline.GetCurrentTimecode.return_value = "01:00:00:00"
        self.mock_timeline.GetTrackCount.return_value = 5

        yield

        self.patcher_config.stop()
        self.patcher_process.stop()

    # teardown_method removed as it's handled by yield above

    @patch("app.core.resolve.ResolveClient._ensure_connected")
    @patch("app.core.resolve.ResolveClient.is_available", return_value=True)
    def test_insert_file_flow(self, mock_is_avail, mock_ensure):
        """Verify the full flow of inserting a file."""
        client = ResolveClient()
        client.resolve = self.mock_resolve
        mock_ensure.return_value = True

        # Mock Media Import
        mock_media_item = MagicMock()
        mock_media_item.GetClipProperty.side_effect = lambda prop: "100" if prop == "Frames" else "00:00:03:10"
        self.mock_media_pool.ImportMedia.return_value = [mock_media_item]

        # Mock Bin Structure for Template
        mock_root = MagicMock()
        self.mock_media_pool.GetRootFolder.return_value = mock_root
        mock_root.GetSubFolderList.return_value = [] # No existing bin, force create
        mock_new_bin = MagicMock()
        self.mock_media_pool.AddSubFolder.return_value = mock_new_bin
        mock_new_bin.GetClipList.return_value = [] # No template found in new bin

        # Run Insertion
        success = client.insert_file("C:/test.wav", text="Hello World")

        assert success is True

        # [Verification 1] ImportMedia called
        self.mock_media_pool.ImportMedia.assert_called_with(["C:/test.wav"])

        # [Verification 2] AppendToTimeline called twice (Audio + Video Template)
        # We expect 2 calls. Call args list has (args, kwargs) tuples.
        # Check Audio Insertion (Track 1 by default)
        calls = self.mock_media_pool.AppendToTimeline.call_args_list
        found_audio = False
        found_video = False

        for call in calls:
            args, _ = call
            item_list = args[0]
            item_data = item_list[0]

            if item_data["mediaType"] == 2: # Audio
                assert item_data["trackIndex"] == 1
                assert item_data["mediaPoolItem"] == mock_media_item
                found_audio = True
            elif item_data["mediaType"] == 1: # Video
                assert item_data["trackIndex"] == 2
                found_video = True

        assert found_audio, "Audio clip was not added to timeline"
        # Video might not be added if template is not found (logic behavior)
        # In our mock above, we returned empty lists so no template found -> no video track insertion.
        assert not found_video

    @patch("app.core.resolve.ResolveClient._ensure_connected")
    @patch("app.core.resolve.ResolveClient.is_available", return_value=True)
    def test_insert_with_template_text_update(self, mock_is_avail, mock_ensure):
        """Verify text update and track logic when template IS found."""
        client = ResolveClient()
        client.resolve = self.mock_resolve
        mock_ensure.return_value = True

        # Mock Media
        self.mock_media_pool.ImportMedia.return_value = [MagicMock()]

        # Mock Template Finding
        mock_root = MagicMock()
        self.mock_media_pool.GetRootFolder.return_value = mock_root

        # Create a mock template clip
        mock_template_clip = MagicMock()
        mock_template_clip.GetClipProperty.side_effect = lambda x: "DefaultTemplate" if x == "Clip Name" else ""

        # Setup recursive search to find it
        mock_root.GetClipList.return_value = [mock_template_clip]
        mock_root.GetSubFolderList.return_value = []

        # Mock Timeline Item (Result of Append)
        mock_timeline_item = MagicMock()
        self.mock_media_pool.AppendToTimeline.return_value = [mock_timeline_item]

        # Mock Fusion Comp
        mock_comp = MagicMock()
        mock_timeline_item.GetFusionCompByIndex.return_value = mock_comp
        mock_tool = MagicMock()
        mock_comp.FindTool.return_value = mock_tool

        # EXECUTE
        client.insert_file("dummy.wav", text="My Subtitle")

        # [Verification 3] Text Injection
        # Ensure FindTool was called with "Template" (or check fallback logic)
        # And SetInput was called with correct text
        mock_tool.SetInput.assert_called_with("StyledText", "My Subtitle")

        # [Verification 4] Track Check
        # API calls to append video should have trackIndex=2 (default)
        # The second call to AppendToTimeline is usually the video one if audio came first
        # But let's check specifically for the one with mediaType=1
        video_call_found = False
        for call in self.mock_media_pool.AppendToTimeline.call_args_list:
            data = call[0][0][0]
            if data['mediaType'] == 1:
                assert data['trackIndex'] == 2
                assert data['mediaPoolItem'] == mock_template_clip
                video_call_found = True

        assert video_call_found, "Template (Video) was not inserted"
