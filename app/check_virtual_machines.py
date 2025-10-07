import logging

from kubernetes import client
from pydantic import BaseModel
from prometheus_client import Counter

log = logging.getLogger("check.virtualmachines")

VIRTUAL_MACHINE_SUCCESS_TOTAL = Counter(
    'virtual_machine_success_total',
    'Total number of successful virtual machine checks',
    ['namespace']
)
VIRTUAL_MACHINE_FAILURE_TOTAL = Counter(
    'virtual_machine_failure_total',
    'Total number of failed virtual machine checks',
    ['namespace']
)


class CheckVirtualMachinesParameters(BaseModel):
    namespace: str
    count: int | None = None


class CheckVirtualMachines:
    def __init__(self, parameters: dict) -> None:
        params = CheckVirtualMachinesParameters(**parameters)
        self.namespace = params.namespace
        self.count = params.count

    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(
            group="vm.cluster.gke.io",
            version="v1",
            plural="virtualmachines",
            namespace=self.namespace,
        )

        # Check for specified count of virtualmachines
        if self.count is not None and len(resp.get("items")) != self.count:
            log.error(
                f'Found {len(resp.get("items"))} virtualmachines but expected {self.count}.'
            )
            VIRTUAL_MACHINE_FAILURE_TOTAL.labels(namespace=self.namespace).inc()
            return False

        # Assert that each virtualmachine is in a healthy state
        healthy_states = ["Running", "Stopped"]

        for virtual_machine in resp.get("items"):
            vm_state = virtual_machine.get("status").get("state")

            if vm_state not in healthy_states:
                log.error(
                    f'VirtualMachine {virtual_machine.get("metadata").get("name")} not in a healthy state. state={vm_state}'
                )
                VIRTUAL_MACHINE_FAILURE_TOTAL.labels(namespace=self.namespace).inc()
                return False

        log.info("Check virtual machines passed")
        VIRTUAL_MACHINE_SUCCESS_TOTAL.labels(namespace=self.namespace).inc()
        return True
