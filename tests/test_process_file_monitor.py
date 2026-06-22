import unittest
from unittest.mock import patch, MagicMock
import yaml
from kuma_ingress_watcher.controller import compute_monitors_from_file


class TestComputeMonitorsFromFile(unittest.TestCase):
    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_empty_file_returns_empty_list(self, mock_open, mock_logger):
        mock_open.return_value.__enter__.return_value.read.return_value = ""
        specs = compute_monitors_from_file("empty_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.info.assert_called_once_with(
            "The file empty_file.yaml is empty or contains only whitespace."
        )

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_invalid_yaml_returns_empty_list(self, mock_open, mock_logger):
        mock_open.return_value.__enter__.return_value.read.return_value = "valid: yaml"
        with patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")):
            specs = compute_monitors_from_file("mock_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.error.assert_called_once_with(
            "Failed to process file mock_file.yaml: Invalid YAML format (Invalid YAML)"
        )

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_file_not_found_returns_empty_list(self, mock_open, mock_logger):
        mock_open.side_effect = FileNotFoundError
        specs = compute_monitors_from_file("nonexistent_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.error.assert_called_once_with("File nonexistent_file.yaml not found.")

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_unexpected_exception_returns_empty_list(self, mock_open, mock_logger):
        mock_open.side_effect = Exception("Unexpected error")
        specs = compute_monitors_from_file("error_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.error.assert_called_once_with(
            "An unexpected error occurred while processing file error_file.yaml: Unexpected error"
        )

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_invalid_entry_format_is_skipped(self, mock_open, mock_logger):
        mock_open.return_value.__enter__.return_value.read.return_value = "- not_a_dict\n"
        specs = compute_monitors_from_file("mock_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.warning.assert_called_once_with(
            "Skipping invalid entry: not_a_dict (Invalid entry format: not_a_dict)"
        )

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_invalid_statuscodes_entry_is_skipped(self, mock_open, mock_logger):
        content = "- name: test\n  url: http://example.com\n  accepted-statuscodes: not_a_list\n"
        mock_open.return_value.__enter__.return_value.read.return_value = content
        specs = compute_monitors_from_file("mock_file.yaml")
        self.assertEqual(specs, [])
        mock_logger.warning.assert_called_once()

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_valid_entry_returns_correct_spec(self, mock_open, mock_logger):
        content = (
            "- name: test-ingress\n"
            "  url: http://example.com\n"
            "  interval: 30\n"
            "  type: http\n"
            "  method: POST\n"
            "  parent: test-parent\n"
            "  accepted-statuscodes:\n"
            "    - 200-299\n"
        )
        mock_open.return_value.__enter__.return_value.read.return_value = content
        specs = compute_monitors_from_file("mock_file.yaml")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "test-ingress")
        self.assertEqual(specs[0].url, "http://example.com")
        self.assertEqual(specs[0].interval, 30)
        self.assertEqual(specs[0].probe_type, "http")
        self.assertEqual(specs[0].method, "POST")
        self.assertEqual(specs[0].parent, "test-parent")
        self.assertEqual(specs[0].accepted_statuscodes, ["200-299"])

    @patch("kuma_ingress_watcher.controller.logger", spec=True)
    @patch("kuma_ingress_watcher.controller.open", new_callable=MagicMock)
    def test_multiple_valid_entries(self, mock_open, mock_logger):
        content = (
            "- name: ingress1\n  url: http://example1.com\n"
            "- name: ingress2\n  url: http://example2.com\n"
            "- name: ingress3\n  url: http://example3.com\n"
        )
        mock_open.return_value.__enter__.return_value.read.return_value = content
        specs = compute_monitors_from_file("mock_file.yaml")
        self.assertEqual(len(specs), 3)
        mock_logger.warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
