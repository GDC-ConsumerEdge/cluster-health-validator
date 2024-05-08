import os
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from kubernetes import config
from prometheus_client import generate_latest, Gauge

from check_data_volumes import CheckDataVolumes
from check_robin_cluster import CheckRobinCluster
from check_node import CheckNode
from check_root_syncs import CheckRootSyncs
from check_virtual_machines import CheckVirtualMachines
from check_vmruntime import CheckVMRuntime
import logging

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper()
)

app = Flask (__name__)

platform_health_metric = Gauge('platform_health', 'Platform Checks')
workload_health_metric = Gauge('workload_health', 'Workload Checks')

@app.route('/metrics')
def metrics():
    return generate_latest()

config.load_config()

def run_platform_checks():
    checks = [CheckNode(), CheckRobinCluster(), CheckRootSyncs(), CheckVMRuntime()]

    all_checks_healthy = True

    for check in checks:
        if (not check.is_healthy()):
            all_checks_healthy = False

    if (all_checks_healthy):
        platform_health_metric.set(1)
    else:
        platform_health_metric.set(0)


def run_workload_configuration_checks():
    checks = [CheckDataVolumes(), CheckVirtualMachines()]

    all_checks_healthy = True

    for check in checks:
        if (not check.is_healthy()):
            all_checks_healthy = False

    if (all_checks_healthy):
        workload_health_metric.set(1)
    else:
        workload_health_metric.set(0)

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_workload_configuration_checks, 'interval',minutes=1)
scheduler.add_job(run_platform_checks, 'interval',minutes=1)
scheduler.start()