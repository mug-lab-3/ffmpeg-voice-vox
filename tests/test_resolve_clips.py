import pytest
from unittest.mock import patch, MagicMock
from app.core.resolve import ResolveClient

class TestResolveClips:
    @patch("app.core.resolve.multiprocessing.Process")
    @patch("app.core.resolve.ResolveClient._ensure_connected", return_value=True)
    @patch("app.core.resolve.ResolveClient.is_available", return_value=True)
    def test_get_text_plus_clips(self, mock_is_avail, mock_ensure, mock_proc_cls):
        client = ResolveClient()
        mock_resolve = MagicMock()
        client.resolve = mock_resolve
        
        mock_pm = MagicMock()
        mock_proj = MagicMock()
        mock_mp = MagicMock()
        mock_root = MagicMock()
        
        mock_resolve.GetProjectManager.return_value = mock_pm
        mock_pm.GetCurrentProject.return_value = mock_proj
        mock_proj.GetMediaPool.return_value = mock_mp
        mock_mp.GetRootFolder.return_value = mock_root
        
        # Mock Bin
        mock_bin = MagicMock()
        mock_bin.GetName.return_value = "TestBin"
        mock_root.GetSubFolderList.return_value = [mock_bin]
        
        # Mock Clips
        clip1 = MagicMock()
        clip1.GetClipProperty.side_effect = lambda p: "Text+" if p == "Type" else ("" if p == "File Path" else "MyClip1")
        
        clip2 = MagicMock()
        clip2.GetClipProperty.side_effect = lambda p: "Fusion" if p == "Type" else ("" if p == "File Path" else "MyClip2")
        
        clip_non_text = MagicMock()
        clip_non_text.GetClipProperty.side_effect = lambda p: "Video" if p == "Type" else ("C:/test.mp4" if p == "File Path" else "VideoClip")
        
        mock_bin.GetClipList.return_value = [clip1, clip2, clip_non_text]
        
        clips = client.get_text_plus_clips("TestBin")
        
        assert "MyClip1" in clips
        assert "MyClip2" in clips
        assert "VideoClip" not in clips
        assert len(clips) == 2

    @patch("app.core.resolve.multiprocessing.Process")
    @patch("app.core.resolve.ResolveClient._ensure_connected", return_value=True)
    @patch("app.core.resolve.ResolveClient.is_available", return_value=True)
    def test_insert_file_error_when_missing(self, mock_is_avail, mock_ensure, mock_proc_cls):
        client = ResolveClient()
        mock_resolve = MagicMock()
        client.resolve = mock_resolve
        
        # Mock to return no clips found
        mock_pm = MagicMock()
        mock_proj = MagicMock()
        mock_mp = MagicMock()
        mock_root = MagicMock()
        mock_resolve.GetProjectManager.return_value = mock_pm
        mock_pm.GetCurrentProject.return_value = mock_proj
        mock_proj.GetMediaPool.return_value = mock_mp
        mock_mp.GetRootFolder.return_value = mock_root
        mock_root.GetSubFolderList.return_value = []
        
        with patch("app.config.config.get", return_value="MissingClip"):
            # Should fail because target_clip_name is "MissingClip" (not auto)
            success = client.insert_file("test.wav", "some text")
            assert success is False
