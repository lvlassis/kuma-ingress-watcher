import unittest
from unittest.mock import patch
from kuma_ingress_watcher.controller import reconcile, MonitorSpec


class TestReconcileCreate(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    def test_creates_missing_monitor_and_tags_it(self, mock_kuma):
        mock_kuma.add_monitor.return_value = {"monitorID": 5}
        desired = {
            "app-default": MonitorSpec(name="app-default", url="https://example.com")
        }
        reconcile(desired, actual={}, groups_map={})
        mock_kuma.add_monitor.assert_called_once_with(
            type="http",
            name="app-default",
            url="https://example.com",
            interval=60,
            headers=None,
            method="GET",
            parent=None,
            accepted_statuscodes=None,
        )
        mock_kuma.add_monitor_tag.assert_called_once_with(
            tag_id=1, monitor_id=5, value=""
        )

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    def test_resolves_parent_group_by_name(self, mock_kuma):
        mock_kuma.add_monitor.return_value = {"monitorID": 5}
        desired = {
            "app": MonitorSpec(name="app", url="https://example.com", parent="my-group")
        }
        groups_map = {"my-group": 99}
        reconcile(desired, actual={}, groups_map=groups_map)
        mock_kuma.add_monitor.assert_called_once_with(
            type="http",
            name="app",
            url="https://example.com",
            interval=60,
            headers=None,
            method="GET",
            parent=99,
            accepted_statuscodes=None,
        )

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    @patch("kuma_ingress_watcher.controller.logger")
    def test_create_failure_logs_error(self, mock_logger, mock_kuma):
        mock_kuma.add_monitor.side_effect = Exception("API error")
        desired = {"app": MonitorSpec(name="app", url="https://example.com")}
        reconcile(desired, actual={}, groups_map={})
        mock_logger.error.assert_called_once()
        mock_kuma.add_monitor_tag.assert_not_called()


if __name__ == "__main__":
    unittest.main()
