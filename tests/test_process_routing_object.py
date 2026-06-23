import unittest
from unittest.mock import patch
from kuma_ingress_watcher.controller import compute_monitors_for_routing_object


class TestComputeMonitorsForRoutingObject(unittest.TestCase):
    def test_single_route_returns_one_spec(self):
        item = {
            "metadata": {"name": "test", "namespace": "default", "annotations": {}},
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "test-default")
        self.assertEqual(specs[0].url, "https://example.com")

    def test_multiple_routes_returns_indexed_specs(self):
        item = {
            "metadata": {"name": "test", "namespace": "default", "annotations": {}},
            "spec": {
                "routes": [
                    {"match": "Host(`example.com`)"},
                    {"match": "Host(`example.org`)"},
                ]
            },
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].name, "test-default-1")
        self.assertEqual(specs[1].name, "test-default-2")

    def test_empty_routes_returns_empty_list(self):
        item = {
            "metadata": {"name": "test", "namespace": "default", "annotations": {}},
            "spec": {"routes": []},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs, [])

    def test_disabled_returns_empty_list(self):
        item = {
            "metadata": {
                "name": "test",
                "namespace": "default",
                "annotations": {"uptime-kuma.autodiscovery.probe.enabled": "false"},
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs, [])

    def test_custom_name_annotation(self):
        item = {
            "metadata": {
                "name": "test",
                "namespace": "default",
                "annotations": {"uptime-kuma.autodiscovery.probe.name": "my-monitor"},
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].name, "my-monitor")

    def test_annotations_are_applied_to_spec(self):
        item = {
            "metadata": {
                "name": "test",
                "namespace": "default",
                "annotations": {
                    "uptime-kuma.autodiscovery.probe.interval": "120",
                    "uptime-kuma.autodiscovery.probe.type": "tcp",
                    "uptime-kuma.autodiscovery.probe.method": "POST",
                    "uptime-kuma.autodiscovery.probe.parent": "my-group",
                    "uptime-kuma.autodiscovery.probe.accepted-statuscodes": '["200-299"]',
                },
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].interval, 120)
        self.assertEqual(specs[0].probe_type, "tcp")
        self.assertEqual(specs[0].method, "POST")
        self.assertEqual(specs[0].parent, "my-group")
        self.assertEqual(specs[0].accepted_statuscodes, ["200-299"])

    def test_invalid_accepted_statuscodes_is_skipped(self):
        item = {
            "metadata": {
                "name": "test",
                "namespace": "default",
                "annotations": {
                    "uptime-kuma.autodiscovery.probe.accepted-statuscodes": "not-a-list",
                },
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertIsNone(specs[0].accepted_statuscodes)

    def test_ingress_type_single_rule(self):
        item = {
            "metadata": {"name": "myapp", "namespace": "prod", "annotations": {}},
            "spec": {"rules": [{"host": "example.com"}]},
        }
        specs = compute_monitors_for_routing_object(item, "Ingress")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "myapp-prod")
        self.assertEqual(specs[0].url, "https://example.com")

    def test_ingress_type_multiple_rules(self):
        item = {
            "metadata": {"name": "myapp", "namespace": "prod", "annotations": {}},
            "spec": {"rules": [{"host": "a.com"}, {"host": "b.com"}]},
        }
        specs = compute_monitors_for_routing_object(item, "Ingress")
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].name, "myapp-prod-1")
        self.assertEqual(specs[1].name, "myapp-prod-2")

    @patch("kuma_ingress_watcher.controller.MONITOR_DEFAULT_NAME", "Cluster - {name}")
    def test_custom_default_name_template(self):
        item = {
            "metadata": {
                "name": "iago-backend",
                "namespace": "default",
                "annotations": {},
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].name, "Cluster - iago-backend")

    @patch(
        "kuma_ingress_watcher.controller.MONITOR_DEFAULT_NAME",
        "Cluster - {name} ({namespace})",
    )
    def test_custom_default_name_template_with_namespace(self):
        item = {
            "metadata": {
                "name": "iago-backend",
                "namespace": "prod",
                "annotations": {},
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].name, "Cluster - iago-backend (prod)")

    @patch("kuma_ingress_watcher.controller.MONITOR_DEFAULT_NAME", "Cluster - {name}")
    def test_annotation_overrides_custom_default_name(self):
        item = {
            "metadata": {
                "name": "iago-backend",
                "namespace": "default",
                "annotations": {
                    "uptime-kuma.autodiscovery.probe.name": "my-custom-name"
                },
            },
            "spec": {"routes": [{"match": "Host(`example.com`)"}]},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].name, "my-custom-name")

    def test_missing_spec_returns_empty_list(self):
        item = {
            "metadata": {"name": "test", "namespace": "default", "annotations": {}},
        }
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs, [])


if __name__ == "__main__":
    unittest.main()
