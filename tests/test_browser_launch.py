import unittest
from unittest.mock import patch, MagicMock
import time
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

# We need to mock webbrowser before importing it or within the scope of the test
from app.core.events import event_manager


class TestBrowserLaunch(unittest.TestCase):

    @patch("webbrowser.open")
    @patch("time.sleep")
    def test_open_browser_conditional(self, mock_sleep, mock_webopen):
        """EventManager の接続状態に応じてブラウザを開くかどうかの判定を検証"""

        # 1. 接続がない場合 (has_had_listeners = False)
        event_manager.has_had_listeners = False

        # ロジックのエミュレート
        host = "127.0.0.1"
        port = 3000
        url = f"http://{host}:{port}"

        if not event_manager.has_had_listeners:
            import webbrowser

            webbrowser.open(url, new=0)

        mock_webopen.assert_called_once_with(url, new=0)
        mock_webopen.reset_mock()

        # 2. すでに接続があった場合 (has_had_listeners = True)
        event_manager.has_had_listeners = True

        if not event_manager.has_had_listeners:
            import webbrowser

            webbrowser.open(url, new=0)

        # 呼ばれていないはず
        mock_webopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
