import unittest
from unittest.mock import patch
from kuma_ingress_watcher.controller import reconcile, _monitor_config_differs, MonitorSpec


class TestMonitorConfigDiffers(unittest.TestCase):
    def _actual(self, **overrides):
        base = {"id": 1, "url": "https://example.com", "type": "http", "interval": 60, "method": "GET", "parent": None}
        base.update(overrides)
        return base

    def test_no_diff_returns_false(self):
        spec = MonitorSpec(name="app", url="https://example.com")
        self.assertFalse(_monitor_config_differs(spec, self._actual(), {}))

    def test_url_change_detected(self):
        spec = MonitorSpec(name="app", url="https://new.com")
        self.assertTrue(_monitor_config_differs(spec, self._actual(), {}))

    def test_interval_change_detected(self):
        spec = MonitorSpec(name="app", url="https://example.com", interval=120)
        self.assertTrue(_monitor_config_differs(spec, self._actual(), {}))

    def test_type_change_detected(self):
        spec = MonitorSpec(name="app", url="https://example.com", probe_type="tcp")
        self.assertTrue(_monitor_config_differs(spec, self._actual(), {}))

    def test_method_change_detected(self):
        spec = MonitorSpec(name="app", url="https://example.com", method="POST")
        self.assertTrue(_monitor_config_differs(spec, self._actual(), {}))

    def test_parent_change_detected(self):
        spec = MonitorSpec(name="app", url="https://example.com", parent="my-group")
        groups_map = {"my-group": 99}
        self.assertTrue(_monitor_config_differs(spec, self._actual(parent=None), groups_map))

    def test_parent_resolved_correctly(self):
        spec = MonitorSpec(name="app", url="https://example.com", parent="my-group")
        groups_map = {"my-group": 99}
        self.assertFalse(_monitor_config_differs(spec, self._actual(parent=99), groups_map))


class TestReconcileUpdate(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.kuma")
    def test_updates_monitor_when_url_changed(self, mock_kuma):
        desired = {"app": MonitorSpec(name="app", url="https://new.com")}
        actual = {"app": {"id": 2, "url": "https://old.com", "type": "http", "interval": 60, "method": "GET", "parent": None}}
        reconcile(desired, actual, groups_map={})
        mock_kuma.edit_monitor.assert_called_once()

    @patch("kuma_ingress_watcher.controller.kuma")
    def test_no_update_when_config_unchanged(self, mock_kuma):
        desired = {"app": MonitorSpec(name="app", url="https://example.com")}
        actual = {"app": {"id": 2, "url": "https://example.com", "type": "http", "interval": 60, "method": "GET", "parent": None}}
        reconcile(desired, actual, groups_map={})
        mock_kuma.edit_monitor.assert_not_called()

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.logger")
    def test_update_failure_logs_error(self, mock_logger, mock_kuma):
        mock_kuma.edit_monitor.side_effect = Exception("API error")
        desired = {"app": MonitorSpec(name="app", url="https://new.com")}
        actual = {"app": {"id": 2, "url": "https://old.com", "type": "http", "interval": 60, "method": "GET", "parent": None}}
        reconcile(desired, actual, groups_map={})
        mock_logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
