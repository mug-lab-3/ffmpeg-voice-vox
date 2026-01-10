
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.config import ConfigManager

class TestResolveToggle(unittest.TestCase):
    def setUp(self):
        # Use a dummy config file
        self.config_file = "test_config.json"
        with open(self.config_file, "w") as f:
            f.write("{}")
        self.config = ConfigManager(self.config_file)

    def tearDown(self):
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

    def test_toggle_logic(self):
        # 1. Default should be False (if not set)
        # Note: defaults are hardcoded in ConfigManager
        
        # 2. Update to True
        self.config.update("resolve.enabled", True)
        self.assertTrue(self.config.get("resolve.enabled"))
        
        # 3. Update to False
        self.config.update("resolve.enabled", False)
        self.assertFalse(self.config.get("resolve.enabled"))
        
        # 4. Update to "false" (string) - simulate bad input
        self.config.update("resolve.enabled", "false")
        # In Python "false" string is truthy if not checked properly?
        # But config just stores what is given.
        self.assertEqual(self.config.get("resolve.enabled"), "false")
        
    @patch("app.core.resolve.ResolveClient")
    def test_audio_manager_integration(self, MockResolve):
        from app.core.audio import AudioManager
        # We need to patch the global config object used in audio.py
        # or mock get_output_dir since we don't want real file IO
        
        with patch("app.core.audio.config", self.config):
            manager = AudioManager()
            
            # Mock filesystem interactions to avoid errors
            with patch("os.path.exists", return_value=True), \
                 patch("os.access", return_value=True), \
                 patch("builtins.open", new_callable=MagicMock), \
                 patch("wave.open", new_callable=MagicMock):
                
                # Case A: Enabled
                self.config.update("resolve.enabled", True)
                # Mock duration return to avoid comparison error
                manager.get_wav_duration = MagicMock(return_value=1.0)
                
                manager.save_audio(b"fake", "text", "speaker", 0, 1000)
                
                # Verify ResolveClient instantiated and insert_file called
                # Note: save_audio runs it in a thread, so we might need to wait or mock threading
                
                # Actually, in save_audio:
                # threading.Thread(target=ResolveClient().insert_file, ...).start()
                # So ResolveClient() is called in the main thread? 
                # No, target=ResolveClient().insert_file instantiates it immediately?
                # "target=ResolveClient().insert_file" -> ResolveClient() is called HERE.
                # YES! ResolveClient() is instantiated in the main thread.
                self.assertTrue(MockResolve.called)
                
                MockResolve.reset_mock()
                
                # Case B: Disabled
                self.config.update("resolve.enabled", False)
                manager.save_audio(b"fake", "text", "speaker", 0, 1000)
                
                self.assertFalse(MockResolve.called, "ResolveClient should not be instantiated when disabled")

if __name__ == "__main__":
    unittest.main()
