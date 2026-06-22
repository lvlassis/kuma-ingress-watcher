import unittest
from unittest.mock import patch
from kuma_ingress_watcher.controller import reconcile, MonitorSpec


class TestReconcileDelete(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.kuma")
    def test_deletes_owned_monitor_not_in_desired(self, mock_kuma):
        actual = {"old-monitor": {"id": 3, "name": "old-monitor", "tags": []}}
        reconcile(desired={}, actual=actual, groups_map={})
        mock_kuma.delete_monitor.assert_called_once_with(3)

    @patch("kuma_ingress_watcher.controller.kuma")
    def test_does_not_delete_desired_monitors(self, mock_kuma):
        desired = {"app": MonitorSpec(name="app", url="https://example.com")}
        actual = {"app": {"id": 1, "name": "app", "url": "https://example.com", "type": "http", "interval": 60, "method": "GET", "parent": None, "tags": []}}
        reconcile(desired, actual, groups_map={})
        mock_kuma.delete_monitor.assert_not_called()

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.logger")
    def test_delete_failure_logs_error(self, mock_logger, mock_kuma):
        mock_kuma.delete_monitor.side_effect = Exception("API error")
        actual = {"old": {"id": 9, "name": "old", "tags": []}}
        reconcile(desired={}, actual=actual, groups_map={})
        mock_logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
