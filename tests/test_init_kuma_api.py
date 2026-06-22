import unittest
from unittest.mock import patch, MagicMock
from kuma_ingress_watcher.controller import init_kuma_api


class TestInitKumaApi(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.get_or_create_ownership_tag", return_value=1)
    @patch("kuma_ingress_watcher.controller.UptimeKumaApi")
    @patch("kuma_ingress_watcher.controller.logger")
    @patch("kuma_ingress_watcher.controller.sys.exit")
    def test_init_kuma_api_success(self, mock_exit, mock_logger, MockUptimeKumaApi, mock_get_tag):
        mock_kuma = MagicMock()
        MockUptimeKumaApi.return_value = mock_kuma

        init_kuma_api()

        mock_kuma.login.assert_called_once()
        mock_get_tag.assert_called_once()
        mock_exit.assert_not_called()

    @patch("kuma_ingress_watcher.controller.UptimeKumaApi")
    @patch("kuma_ingress_watcher.controller.logger")
    @patch("kuma_ingress_watcher.controller.sys.exit")
    def test_init_kuma_api_failure(self, mock_exit, mock_logger, MockUptimeKumaApi):
        MockUptimeKumaApi.side_effect = Exception("Login failed")

        init_kuma_api()

        mock_exit.assert_called_once_with(1)
        mock_logger.error.assert_called_once()

    @patch("kuma_ingress_watcher.controller.get_or_create_ownership_tag", return_value=42)
    @patch("kuma_ingress_watcher.controller.UptimeKumaApi")
    @patch("kuma_ingress_watcher.controller.logger")
    @patch("kuma_ingress_watcher.controller.sys.exit")
    def test_init_kuma_api_sets_ownership_tag_id(self, mock_exit, mock_logger, MockUptimeKumaApi, mock_get_tag):
        import kuma_ingress_watcher.controller as ctrl
        MockUptimeKumaApi.return_value = MagicMock()

        init_kuma_api()

        self.assertEqual(ctrl.ownership_tag_id, 42)


if __name__ == "__main__":
    unittest.main()
