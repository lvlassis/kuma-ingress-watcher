import os
import re
import time
import logging
import sys
import yaml
from dataclasses import dataclass
from typing import Optional
from uptime_kuma_api import UptimeKumaApi, MonitorType
from kubernetes import client, config


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ["true", "1", "t", "y", "yes"]


# Configuration
UPTIME_KUMA_URL = os.getenv("UPTIME_KUMA_URL")
UPTIME_KUMA_USER = os.getenv("UPTIME_KUMA_USER")
UPTIME_KUMA_PASSWORD = os.getenv("UPTIME_KUMA_PASSWORD")
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "10") or 10)
WATCH_INGRESSROUTES = str_to_bool(os.getenv("WATCH_INGRESSROUTES", True))
WATCH_INGRESS = str_to_bool(os.getenv("WATCH_INGRESS", False))
USE_TRAEFIK_V3_CRD_GROUP = str_to_bool(os.getenv("USE_TRAEFIK_V3_CRD_GROUP", False))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOAD_MONITOR_FROM_FILE = str_to_bool(os.getenv("ENABLE_FILE_MONITOR", False))
FILE_MONITOR_PATH = os.getenv("FILE_MONITOR_PATH", "/etc/kuma-controller/monitors.yaml")
DEFAULT_PARENT = os.getenv("DEFAULT_PARENT", None)
MONITOR_DEFAULT_NAME = os.getenv("MONITOR_DEFAULT_NAME", "{name}-{namespace}")

OWNERSHIP_TAG_NAME = "kuma-ingress-watcher"
OWNERSHIP_TAG_COLOR = "#3b82f6"

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

logging.basicConfig(
    level=LOG_LEVELS.get(LOG_LEVEL, "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

kuma = None
ownership_tag_id = None
custom_api_instance = None
networking_api_instance = None


@dataclass
class MonitorSpec:
    name: str
    url: str
    interval: int = 60
    probe_type: str = "http"
    headers: Optional[str] = None
    method: str = "GET"
    parent: Optional[str] = None
    accepted_statuscodes: Optional[list] = None


def check_config():
    if not UPTIME_KUMA_URL or not UPTIME_KUMA_USER or not UPTIME_KUMA_PASSWORD:
        logger.error("Uptime Kuma configuration is not set properly.")
        sys.exit(1)


def get_or_create_ownership_tag() -> int:
    tags = kuma.get_tags()
    existing = next((t for t in tags if t["name"] == OWNERSHIP_TAG_NAME), None)
    if existing:
        logger.info(f"Using existing ownership tag: id={existing['id']}")
        return existing["id"]
    result = kuma.add_tag(name=OWNERSHIP_TAG_NAME, color=OWNERSHIP_TAG_COLOR)
    logger.info(f"Created ownership tag: id={result['id']}")
    return result["id"]


def init_kuma_api():
    try:
        global kuma, ownership_tag_id
        kuma = UptimeKumaApi(UPTIME_KUMA_URL)
        kuma.login(UPTIME_KUMA_USER, UPTIME_KUMA_PASSWORD)
        ownership_tag_id = get_or_create_ownership_tag()
    except Exception as e:
        logger.error(f"Failed to connect to Uptime Kuma API: {e}")
        sys.exit(1)


def extract_hosts_from_match(match):
    host_pattern = re.compile(r"Host\(`([^`]*)`\)")
    return host_pattern.findall(match)


def extract_hosts_from_ingress_rule(rule):
    hosts = []
    if "host" in rule:
        hosts.append(rule["host"])
    return hosts


def extract_hosts(route_or_rule, type_obj):
    if type_obj == "IngressRoute":
        match = route_or_rule.get("match")
        return extract_hosts_from_match(match) if match else []
    elif type_obj == "Ingress":
        return extract_hosts_from_ingress_rule(route_or_rule)
    else:
        return []


def get_routes_or_rules(spec, type_obj):
    if type_obj == "IngressRoute":
        return spec.get("routes", [])
    elif type_obj == "Ingress":
        return spec.get("rules", [])
    else:
        return []


def compute_monitors_for_routing_object(item, type_obj) -> list[MonitorSpec]:
    metadata = item["metadata"]
    annotations = metadata.get("annotations") or {}
    name = metadata["name"]
    namespace = metadata["namespace"]
    spec = item.get("spec") or {}

    enabled = annotations.get("uptime-kuma.autodiscovery.probe.enabled", "true").lower() == "true"
    if not enabled:
        return []

    routes_or_rules = get_routes_or_rules(spec, type_obj)
    interval = int(annotations.get("uptime-kuma.autodiscovery.probe.interval", 60))
    monitor_name = annotations.get(
        "uptime-kuma.autodiscovery.probe.name",
        MONITOR_DEFAULT_NAME.replace("{name}", name).replace("{namespace}", namespace),
    )
    probe_type = annotations.get("uptime-kuma.autodiscovery.probe.type", "http")
    headers = annotations.get("uptime-kuma.autodiscovery.probe.headers")
    port = annotations.get("uptime-kuma.autodiscovery.probe.port")
    path = annotations.get("uptime-kuma.autodiscovery.probe.path")
    hard_host = annotations.get("uptime-kuma.autodiscovery.probe.host")
    method = annotations.get("uptime-kuma.autodiscovery.probe.method", "GET")
    parent = annotations.get("uptime-kuma.autodiscovery.probe.parent", DEFAULT_PARENT)
    accepted_statuscodes = annotations.get("uptime-kuma.autodiscovery.probe.accepted-statuscodes")

    if accepted_statuscodes:
        try:
            accepted_statuscodes = yaml.safe_load(accepted_statuscodes)
            if type(accepted_statuscodes) is not list:
                raise ValueError("accepted-statuscodes must be a list")
        except (ValueError, yaml.YAMLError):
            logger.warning(f"Failed to process accepted-statuscodes for {name}, skipping")
            accepted_statuscodes = None

    specs = []
    index = 1
    for route_or_rule in routes_or_rules:
        hosts = extract_hosts(route_or_rule, type_obj)
        if hosts:
            for host in hosts:
                url = f"https://{hard_host if hard_host else host}"
                if path:
                    url = f"{url}{path}"
                if port:
                    url = f"{url}:{port}"

                indexed_name = f"{monitor_name}-{index}" if len(routes_or_rules) > 1 else monitor_name
                specs.append(MonitorSpec(
                    name=indexed_name,
                    url=url,
                    interval=interval,
                    probe_type=probe_type,
                    headers=headers,
                    method=method,
                    parent=parent,
                    accepted_statuscodes=accepted_statuscodes,
                ))
            index += 1

    return specs


def compute_monitors_from_file(file_path) -> list[MonitorSpec]:
    specs = []
    try:
        with open(file_path, "r") as f:
            content = f.read()

        if not content.strip():
            logger.info(f"The file {file_path} is empty or contains only whitespace.")
            return []

        try:
            entries = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.error(f"Failed to process file {file_path}: Invalid YAML format ({e})")
            return []

        for entry in entries:
            try:
                if not isinstance(entry, dict):
                    raise ValueError(f"Invalid entry format: {entry}")
                if "name" not in entry or "url" not in entry:
                    raise KeyError(f"Missing required fields in entry: {entry}")

                statuscodes = entry.get("accepted-statuscodes")
                if statuscodes is not None and type(statuscodes) is not list:
                    raise ValueError("Invalid entry format - accepted-statuscodes must be a list")

                specs.append(MonitorSpec(
                    name=entry["name"],
                    url=entry["url"],
                    interval=entry.get("interval", 60),
                    probe_type=entry.get("type", "http"),
                    headers=entry.get("headers", {}),
                    method=entry.get("method", "GET"),
                    parent=entry.get("parent"),
                    accepted_statuscodes=statuscodes,
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid entry: {entry} ({str(e)})")

    except FileNotFoundError:
        logger.error(f"File {file_path} not found.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while processing file {file_path}: {str(e)}")

    return specs


def compute_desired_state() -> dict[str, MonitorSpec]:
    desired = {}

    if WATCH_INGRESSROUTES:
        for item in get_ingressroutes(custom_api_instance)["items"]:
            for spec in compute_monitors_for_routing_object(item, "IngressRoute"):
                desired[spec.name] = spec

    if WATCH_INGRESS:
        for item in get_ingress(networking_api_instance)["items"]:
            for spec in compute_monitors_for_routing_object(item, "Ingress"):
                desired[spec.name] = spec

    if LOAD_MONITOR_FROM_FILE:
        for spec in compute_monitors_from_file(FILE_MONITOR_PATH):
            desired[spec.name] = spec

    return desired


def _monitor_config_differs(spec: MonitorSpec, monitor: dict, groups_map: dict) -> bool:
    desired_parent_id = groups_map.get(spec.parent) if spec.parent else None
    return any([
        str(spec.url) != str(monitor.get("url", "")),
        int(spec.interval) != int(monitor.get("interval", 60)),
        str(spec.probe_type) != str(monitor.get("type", "")),
        str(spec.method).upper() != str(monitor.get("method", "GET")).upper(),
        desired_parent_id != monitor.get("parent"),
    ])


def reconcile(desired: dict[str, MonitorSpec], actual: dict[str, dict], groups_map: dict):
    desired_names = set(desired.keys())
    actual_names = set(actual.keys())

    for name in desired_names - actual_names:
        spec = desired[name]
        try:
            result = kuma.add_monitor(
                type=spec.probe_type,
                name=spec.name,
                url=spec.url,
                interval=spec.interval,
                headers=spec.headers,
                method=spec.method,
                parent=groups_map.get(spec.parent) if spec.parent else None,
                accepted_statuscodes=spec.accepted_statuscodes,
            )
            kuma.add_monitor_tag(tag_id=ownership_tag_id, monitor_id=result["monitorID"], value="")
            logger.info(f"Created monitor {name}")
        except Exception as e:
            logger.error(f"Failed to create monitor {name}: {e}")

    for name in actual_names - desired_names:
        try:
            kuma.delete_monitor(actual[name]["id"])
            logger.info(f"Deleted monitor {name}")
        except Exception as e:
            logger.error(f"Failed to delete monitor {name}: {e}")

    for name in desired_names & actual_names:
        spec = desired[name]
        monitor = actual[name]
        if _monitor_config_differs(spec, monitor, groups_map):
            try:
                kuma.edit_monitor(
                    monitor["id"],
                    url=spec.url,
                    type=spec.probe_type,
                    headers=spec.headers,
                    method=spec.method,
                    interval=spec.interval,
                    parent=groups_map.get(spec.parent) if spec.parent else None,
                    accepted_statuscodes=spec.accepted_statuscodes,
                )
                logger.info(f"Updated monitor {name}")
            except Exception as e:
                logger.error(f"Failed to update monitor {name}: {e}")


def init_kubernetes_client():
    try:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        if WATCH_INGRESS:
            global networking_api_instance
            networking_api_instance = client.NetworkingV1Api()

        if WATCH_INGRESSROUTES:
            global custom_api_instance
            custom_api_instance = client.CustomObjectsApi()
    except Exception as e:
        logger.error(f"Failed to initialize Kubernetes client: {e}")
        sys.exit(1)


def get_ingressroutes(custom_api_instance):
    group = "traefik.io" if USE_TRAEFIK_V3_CRD_GROUP else "traefik.containo.us"
    try:
        return custom_api_instance.list_cluster_custom_object(
            group=group, version="v1alpha1", plural="ingressroutes"
        )
    except Exception as e:
        logger.error(f"Failed to get ingressroutes: {e}")
        return {"items": []}


def get_ingress(networking_api_instance):
    try:
        ingress_list = networking_api_instance.list_ingress_for_all_namespaces()
        return {"items": [ingress.to_dict() for ingress in ingress_list.items]}
    except Exception as e:
        logger.error(f"Failed to get Ingress: {e}")
        return {"items": []}


def reconciliation_loop():
    logger.info("Starting reconciliation loop")
    while True:
        try:
            all_monitors = kuma.get_monitors()
            groups_map = {m["name"]: m["id"] for m in all_monitors if m.get("type") == MonitorType.GROUP}
            actual = {
                m["name"]: m
                for m in all_monitors
                if any(t["tag_id"] == ownership_tag_id for t in m.get("tags", []))
            }
            desired = compute_desired_state()
            reconcile(desired, actual, groups_map)
        except Exception as e:
            logger.error(f"Reconciliation error: {e}")

        time.sleep(WATCH_INTERVAL)


def main():
    check_config()
    init_kuma_api()

    if WATCH_INGRESSROUTES or WATCH_INGRESS:
        init_kubernetes_client()

    if WATCH_INGRESSROUTES or WATCH_INGRESS or LOAD_MONITOR_FROM_FILE:
        reconciliation_loop()
    else:
        logger.warning("Nothing to watch. Set WATCH_INGRESSROUTES, WATCH_INGRESS, or ENABLE_FILE_MONITOR.")


if __name__ == "__main__":
    main()
