import unittest
from kuma_ingress_watcher.controller import compute_monitors_for_routing_object


class TestComputeMonitorsUrlConstruction(unittest.TestCase):
    def _item(self, annotations=None, routes=None):
        return {
            "metadata": {
                "name": "test",
                "namespace": "default",
                "annotations": annotations or {},
            },
            "spec": {"routes": routes or [{"match": "Host(`example.com`)"}]},
        }

    def test_url_with_port(self):
        item = self._item(annotations={"uptime-kuma.autodiscovery.probe.port": "8080"})
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].url, "https://example.com:8080")

    def test_url_with_path(self):
        item = self._item(
            annotations={"uptime-kuma.autodiscovery.probe.path": "/milou"}
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].url, "https://example.com/milou")

    def test_url_with_hard_host(self):
        item = self._item(
            annotations={"uptime-kuma.autodiscovery.probe.host": "tintin"}
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].url, "https://tintin")

    def test_url_with_hard_host_and_path(self):
        item = self._item(
            annotations={
                "uptime-kuma.autodiscovery.probe.host": "tintin",
                "uptime-kuma.autodiscovery.probe.path": "/milou",
            }
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].url, "https://tintin/milou")

    def test_url_with_hard_host_and_path_and_port(self):
        item = self._item(
            annotations={
                "uptime-kuma.autodiscovery.probe.host": "tintin",
                "uptime-kuma.autodiscovery.probe.path": "/milou",
                "uptime-kuma.autodiscovery.probe.port": "8080",
            }
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].url, "https://tintin:8080/milou")

    def test_multi_route_with_hard_host_uses_same_host_for_all(self):
        item = self._item(
            annotations={"uptime-kuma.autodiscovery.probe.host": "tintin"},
            routes=[{"match": "Host(`a.com`)"}, {"match": "Host(`b.com`)"}],
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].url, "https://tintin")
        self.assertEqual(specs[1].url, "https://tintin")

    def test_route_without_host_is_skipped(self):
        item = self._item(routes=[{"match": "Path(`/health`)"}])
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs, [])

    def test_multi_route_one_without_host_skips_it(self):
        item = self._item(
            routes=[
                {"match": "Path(`/health`)"},
                {"match": "Host(`example.com`)"},
            ]
        )
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "test-default-1")

    def test_single_route_no_index_suffix(self):
        item = self._item(routes=[{"match": "Host(`example.com`)"}])
        specs = compute_monitors_for_routing_object(item, "IngressRoute")
        self.assertEqual(specs[0].name, "test-default")


if __name__ == "__main__":
    unittest.main()
