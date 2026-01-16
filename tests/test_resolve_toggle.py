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
        self.config_filename = "test_config_toggle.json"
        self.config_path = os.path.join("data", self.config_filename)
        # Ensure cleanup first
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

        self.config = ConfigManager(self.config_filename)
        # Ensure output dir is set for audio tests
        self.config.system.output_dir = "dummy_out"
        self.config.save_config_ex()

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_toggle_logic(self):
        # 1. Default should be False (if not set)
        assert self.config.is_synthesis_enabled is False

        # 2. Update to True
        self.config.is_synthesis_enabled = True
        self.assertTrue(self.config.is_synthesis_enabled)

        # 3. Update to False
        self.config.is_synthesis_enabled = False
        self.assertFalse(self.config.is_synthesis_enabled)


if __name__ == "__main__":
    unittest.main()
