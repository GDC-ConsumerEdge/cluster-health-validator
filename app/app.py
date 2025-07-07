import concurrent.futures
import logging
import os

import requests
from apscheduler.schedulers import base
from apscheduler.schedulers.background import BackgroundScheduler
from check_data_volumes import CheckDataVolumes
from check_google_group_rbac import CheckGoogleGroupRBAC
from check_network_speed import CheckNetworkSpeed
from check_nodes import CheckNodes
from check_ping import CheckPing
from check_robin_cluster import CheckRobinCluster
from check_root_syncs import CheckRootSyncs
from check_virtual_machines import CheckVirtualMachines
from check_vmruntime import CheckVMRuntime
from config import read_config
from flask import Flask, abort
from health_checks import HealthCheck
from kubernetes import config
from kubernetes.client.exceptions import ApiException
from prometheus_client import Gauge, generate_latest

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())

app = Flask(__name__)

platform_health_metric = Gauge("platform_health", "Platform Checks")
workload_health_metric = Gauge("workload_health", "Workload Checks")
network_health_metric = Gauge("network_health", "Network Checks")

_MAX_WORKERS = os.environ.get("MAX_WORKERS", 10)
_ROBIN_MASTER_SVC_ENDPOINT = "robin-master.robinio.svc.cluster.local"
_ROBIN_MASTER_SVC_METRICS_PORT = 29446

health_check_map = {
    CheckGoogleGroupRBAC.__name__: CheckGoogleGroupRBAC,
    CheckNodes.__name__: CheckNodes,
    CheckRobinCluster.__name__: CheckRobinCluster,
    CheckRootSyncs.__name__: CheckRootSyncs,
    CheckVMRuntime.__name__: CheckVMRuntime,
    CheckDataVolumes.__name__: CheckDataVolumes,
    CheckVirtualMachines.__name__: CheckVirtualMachines,
    CheckPing.__name__: CheckPing,
    CheckNetworkSpeed.__name__: CheckNetworkSpeed,
}

platform_checks = []
workload_checks = []
network_checks = []
app_config = None

@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint for workload and platform checks"""
    return generate_latest()


# requests is used only to query the robin metrics endpoint to proxy metrics
# Since robin uses a self-signed cert, disabling warning to avoid
#   `InsecureRequestWarning: Unverified HTTPS request is being made to host` errors
requests.packages.urllib3.disable_warnings()


@app.route("/robin_metrics")
def robin_metrics():
    """Queries and returns robin metrics available from the robin-master service.
    This endpoint serves up robin metrics on an http endpoint, which allows
    prometheus scraping from stackdriver.
    """
    url = (
        f"https://{_ROBIN_MASTER_SVC_ENDPOINT}:{_ROBIN_MASTER_SVC_METRICS_PORT}/metrics"
    )
    response = requests.get(url, verify=False, timeout=10)
    return response.text


def create_health_check_cr():
    """To create health check resource. It is invoked for each healthcheck
    schedule as configsync apply may create pod first and clusterrolebinding
    later which makes the CR creation fail."""
    try:
        return HealthCheck()
    except Exception:  # pylint: disable=broad-except
        logging.error("Failed to setup healthcheck CR", exc_info=True)
        logging.error("Health status will not updated in k8s CR")
    return None

def generate_health_checks_from_config(check_config):
    checks = []

    for check in check_config:
        if "parameters" in check:
            checks.append(
                health_check_map[check["module"]](check["parameters"])
            )
        else:
            checks.append(health_check_map[check["module"]]())

    return checks

def initialize_health_checks():
    global health_check_cr
    if not health_check_cr:
        health_check_cr = HealthCheck()

    new_config = read_config()

    global app_config

    # Check if health check configuration has changed and needs to be reloaded
    if new_config != app_config:
        logging.info("Loading new health check configuration")
        app_config = new_config

        global platform_checks, workload_checks, network_checks
        platform_checks = generate_health_checks_from_config(app_config.platform_checks)
        workload_checks = generate_health_checks_from_config(app_config.workload_checks)
        network_checks = generate_health_checks_from_config(app_config.network_checks)


def run_checks():
    initialize_health_checks()

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        platform_checks_futures = {
            executor.submit(check.is_healthy): check.__class__.__name__
            for check in platform_checks
        }
        workload_checks_futures = {
            executor.submit(check.is_healthy): check.__class__.__name__
            for check in workload_checks
        }
        network_checks_futures = {
            executor.submit(check.is_healthy): check.__class__.__name__
            for check in network_checks
        }

        def wait_on_futures(futures, health_metric):
            if len(futures) == 0 or futures is None:
                return None

            checks_failed = []
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    if not future.result():
                        checks_failed.append(name)
                # Handling k8s resource not found here as it is not
                # handled in the individual checks.
                except ApiException as e:
                    if e.status == 404:
                        checks_failed.append(name)
                    else:
                        raise

            if checks_failed:
                health_metric.set(0)
            else:
                health_metric.set(1)
            
            return checks_failed

        platform_checks_failed = wait_on_futures(platform_checks_futures, platform_health_metric)
        workload_checks_failed = wait_on_futures(workload_checks_futures, workload_health_metric)
        network_checks_failed = wait_on_futures(network_checks_futures, network_health_metric)

        logging.debug("Platform checks failed: %s", platform_checks_failed)
        logging.debug("Workload checks failed: %s", workload_checks_failed)
        logging.debug("Network checks failed: %s", network_checks_failed)

        if health_check_cr:
            health_check_cr.update_status(
                platform_checks_failed, workload_checks_failed, network_checks_failed
            )


config.load_config()
health_check_cr = create_health_check_cr()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_checks, "interval", minutes=1)
scheduler.start()


@app.route("/health")
def health():
    """health endpoint that confirms the health check scheduler is running"""

    # 0 == stopped, 1 == running, 2 == paused
    if scheduler.state != base.STATE_RUNNING:
        abort(500, "Scheduler not running")

    return "Ok"