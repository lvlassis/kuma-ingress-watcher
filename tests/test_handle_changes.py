import unittest
from unittest.mock import patch, MagicMock
from kuma_ingress_watcher.controller import reconcile, MonitorSpec


class TestReconcileIntegration(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    def test_create_update_delete_in_single_pass(self, mock_kuma):
        mock_kuma.add_monitor.return_value = {"monitorID": 10}

        desired = {
            "new-app": MonitorSpec(name="new-app", url="https://new.com"),
            "existing-app": MonitorSpec(name="existing-app", url="https://updated.com"),
        }
        actual = {
            "existing-app": {"id": 1, "url": "https://old.com", "type": "http", "interval": 60, "method": "GET", "parent": None},
            "orphan": {"id": 2, "url": "https://orphan.com"},
        }

        reconcile(desired, actual, groups_map={})

        mock_kuma.add_monitor.assert_called_once()
        mock_kuma.edit_monitor.assert_called_once()
        mock_kuma.delete_monitor.assert_called_once_with(2)

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    def test_empty_desired_deletes_all_owned(self, mock_kuma):
        actual = {
            "a": {"id": 1, "url": "https://a.com"},
            "b": {"id": 2, "url": "https://b.com"},
        }
        reconcile(desired={}, actual=actual, groups_map={})
        self.assertEqual(mock_kuma.delete_monitor.call_count, 2)
        mock_kuma.add_monitor.assert_not_called()

    @patch("kuma_ingress_watcher.controller.kuma")
    @patch("kuma_ingress_watcher.controller.ownership_tag_id", 1)
    def test_empty_actual_creates_all_desired(self, mock_kuma):
        mock_kuma.add_monitor.return_value = {"monitorID": 5}
        desired = {
            "a": MonitorSpec(name="a", url="https://a.com"),
            "b": MonitorSpec(name="b", url="https://b.com"),
        }
        reconcile(desired, actual={}, groups_map={})
        self.assertEqual(mock_kuma.add_monitor.call_count, 2)
        mock_kuma.delete_monitor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
