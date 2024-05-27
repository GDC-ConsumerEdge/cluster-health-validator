from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from kubernetes import config
from kubernetes.client.exceptions import ApiException
from prometheus_client import generate_latest, Gauge
import logging
import os
import concurrent.futures

from check_data_volumes import CheckDataVolumes
from check_robin_cluster import CheckRobinCluster
from check_node import CheckNode
from check_root_syncs import CheckRootSyncs
from check_virtual_machines import CheckVirtualMachines
from check_vmruntime import CheckVMRuntime
from health_checks import HealthCheck

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())

app = Flask(__name__)

platform_health_metric = Gauge('platform_health', 'Platform Checks')
workload_health_metric = Gauge('workload_health', 'Workload Checks')

_MAX_WORKERS = os.environ.get('MAX_WORKERS', 10)


@app.route('/metrics')
def metrics():
    return generate_latest()


def run_checks():
    platform_checks = [
        CheckNode(),
        CheckRobinCluster(),
        CheckRootSyncs(),
        CheckVMRuntime(),
    ]
    workload_checks = [
        CheckDataVolumes(),
        CheckVirtualMachines(),
    ]
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_WORKERS) as executor:
        platform_checks_futures = {
            executor.submit(check.is_healthy): check.__class__.__name__
            for check in platform_checks
        }
        workload_checks_futures = {
            executor.submit(check.is_healthy): check.__class__.__name__
            for check in workload_checks
        }

        def wait_on_futures(futures):
            checks_failed = []
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    if not future.result():
                        checks_failed.append(name)
                # Handling k8s resource not found here as it is not handled in the individual checks.
                except ApiException as e:
                    if e.status == 404:
                        checks_failed.append(name)
                    else:
                        raise
            return checks_failed

        platform_checks_failed = wait_on_futures(platform_checks_futures)
        workload_checks_failed = wait_on_futures(workload_checks_futures)

        if platform_checks_failed:
            platform_health_metric.set(0)
        else:
            platform_health_metric.set(1)

        if workload_checks_failed:
            workload_health_metric.set(0)
        else:
            workload_health_metric.set(1)

        if health_check_cr:
            health_check_cr.update_status(platform_checks_failed,
                                          workload_checks_failed)


config.load_config()
try:
    health_check_cr = HealthCheck()
except Exception as e:
    health_check_cr = None
    logging.error("Failed to setup healthcheck CR", exc_info=True)
    logging.error("Health status will not updated in k8s CR")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_checks, 'interval', minutes=1)
scheduler.start()