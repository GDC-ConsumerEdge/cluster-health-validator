"""Exposes HealthCheck CR on k8s for GDCC cluster health validator."""
from dataclasses import dataclass, asdict, field
from datetime import datetime
from kubernetes import config, client
from kubernetes.client.exceptions import ApiException
from os import path
from typing import List, Dict, Any
import time
import yaml

_CRD_FILE_PATH = path.join(path.dirname(__file__), "healthchecks.crd.yaml")
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class HealthCheck:
    """Class for GDCC cluster health checks"""
    group = "validator.gdc.gke.io"
    version = "v1"
    kind = "HealthCheck"
    plural = "healthchecks"
    name = "default"
    meta = {
        "apiVersion": f'{group}/{version}',
        "kind": kind,
        "metadata": {
            "name": name,
        }
    }

    @dataclass
    class HealthCheckCondition:
        """Class for HealthCheck conditions"""
        type: str
        message: str
        reason: str
        status: str
        lastUpdateTime: str = field(default="", compare=False)
        lastTransitionTime: str = field(default="", compare=False)

        def to_dict(self) -> Dict[Any, Any]:
            return asdict(self)

    def __init__(self):
        config.load_config()
        self.crd_api = client.ApiextensionsV1Api()
        self.customobjects_api = client.CustomObjectsApi()

        date_time_now = datetime.now().strftime(_DATETIME_FORMAT)
        self.condition_platform = self.HealthCheckCondition(
            type="PlatformHealthy",
            status="Unknown",
            reason="Pending",
            message="Checks not run yet",
            lastTransitionTime=date_time_now,
            lastUpdateTime=date_time_now,
        )
        self.condition_workloads = self.HealthCheckCondition(
            type="WorkloadsHealthy",
            status="Unknown",
            reason="Pending",
            message="Checks not run yet",
            lastTransitionTime=date_time_now,
            lastUpdateTime=date_time_now,
        )

        if not self.is_crd_installed():
            self.install_crd()

        if not self.is_resource_present():
            self.create()
        else:
            # Load the current conditions if present
            health_check_resource = self.get()
            # ignore initializing if we cannot fetch two conditions
            if "status" in health_check_resource and "conditions" in health_check_resource[
                    "status"] and len(
                        health_check_resource["status"]["conditions"]) == 2:
                self.condition_platform = self.HealthCheckCondition(
                    **health_check_resource["status"]["conditions"][0])
                self.condition_workloads = self.HealthCheckCondition(
                    **health_check_resource["status"]["conditions"][1])

    def install_crd(self):
        """Install custom resource definition."""
        with open(_CRD_FILE_PATH, "r") as f:
            crd_manifest = yaml.safe_load(f)
        self.crd_api.create_custom_resource_definition(body=crd_manifest)
        while not self.is_crd_installed():
            time.sleep(2)

    def is_crd_installed(self):
        """Check if healtcheckcustom resource definition is installed."""
        try:
            self.crd_api.read_custom_resource_definition(
                name=f'{self.plural}.{self.group}')
        except ApiException as e:
            if e.status == 404:
                return False
            raise
        return True

    def is_resource_present(self):
        """Check if default healtcheck resource is present."""
        try:
            self.get()
        except ApiException as e:
            if e.status == 404:
                return False
            raise
        return True

    def create(self):
        """Create default healtcheck resource."""
        spec = {"spec": {"enabled": True}}
        status = {
            "status": {
                "conditions": [
                    self.condition_platform.to_dict(),
                    self.condition_workloads.to_dict(),
                ]
            }
        }
        self.customobjects_api.create_cluster_custom_object(
            group=self.group,
            version=self.version,
            plural=self.plural,
            body=self.meta | spec,
        )
        time.sleep(2)  # adding a delay between create and update status
        self.customobjects_api.patch_cluster_custom_object_status(
            group=self.group,
            version=self.version,
            plural=self.plural,
            name=self.name,
            body=status,
        )

    def get(self) -> Dict[str, Any]:
        """Get default healtcheck resource.
        Returns:
            custom resource: default healtcheck resource
        """
        return self.customobjects_api.get_cluster_custom_object(
            group=self.group,
            version=self.version,
            plural=self.plural,
            name=self.name,
        )

    def update_condition(self, condition: HealthCheckCondition,
                         failed_checks: List[str]) -> None:
        """Updates HealthCheckCondition fields.
        Args:
            condition: HealthCheck condition platform or workload
            failed_checks: List of failed checks
        """
        date_time_now = datetime.now().strftime(_DATETIME_FORMAT)
        previous_status = condition.status
        if failed_checks:
            condition.status = "False"
            condition.reason = "HealthChecksFailed"
            condition.message = "Failed checks: " + ",".join(failed_checks)
        else:
            condition.status = "True"
            condition.reason = "HealthChecksPassed"
            condition.message = ""

        condition.lastUpdateTime = date_time_now
        if previous_status != condition.status:
            condition.lastTransitionTime = date_time_now

    def update_status(
        self,
        failed_platform_checks: List[str],
        failed_workload_checks: List[str],
    ) -> None:
        """Updates default healthcheck resource status.
        Args:
            failed_platform_checks: List of failed platform checks
            failed_workload_checks: List of failed workload checks
        """
        self.update_condition(self.condition_platform, failed_platform_checks)
        self.update_condition(self.condition_workloads, failed_workload_checks)
        patch = {
            "status": {
                "conditions": [
                    self.condition_platform.to_dict(),
                    self.condition_workloads.to_dict(),
                ]
            }
        }
        self.customobjects_api.patch_cluster_custom_object_status(
            group=self.group,
            version=self.version,
            plural=self.plural,
            name=self.name,
            body=self.meta | patch,
        )
