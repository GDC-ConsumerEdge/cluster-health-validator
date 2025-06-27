import logging

from kubernetes import client
from pydantic import BaseModel

log = logging.getLogger("check.virtualmachines")


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
            return False

        # Assert that each virtualmachine is in a healthy state
        healthy_states = ["Running", "Stopped"]

        for virtual_machine in resp.get("items"):
            vm_state = virtual_machine.get("status").get("state")

            if vm_state not in healthy_states:
                log.error(
                    f'VirtualMachine {virtual_machine.get("metadata").get("name")} not in a healthy state. state={vm_state}'
                )
                return False

        log.info("Check virtual machines passed")
        return True
