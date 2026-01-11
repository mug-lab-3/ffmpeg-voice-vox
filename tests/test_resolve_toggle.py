
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
        self.config.update("system.output_dir", "dummy_out")

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

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
        self.assertEqual(self.config.get("resolve.enabled"), False)



if __name__ == "__main__":
    unittest.main()
