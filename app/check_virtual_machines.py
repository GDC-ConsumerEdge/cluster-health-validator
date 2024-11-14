from kubernetes import client
from pydantic import BaseModel
import logging

log = logging.getLogger('check.virtualmachines')

class CheckVirtualMachinesParameters(BaseModel):
    namespace: str
    count: int

class CheckVirtualMachines:
    def __init__(self, parameters: dict) -> None:
        params = CheckVirtualMachinesParameters(**parameters)
        self.namespace = params.namespace
        self.count = params.count

    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(group="vm.cluster.gke.io", version="v1", plural="virtualmachines", namespace=self.namespace)

        # Expect multiple virtualmachines
        if (len(resp.get("items")) != self.count):
            log.error(f'Found {len(resp.get("items"))} virtualmachines but expected {self.count}.')
            return False

        # Assert that each virtualmachine is running
        for virtual_machine in resp.get("items"):
            if (virtual_machine.get("status").get("state") != "Running"):
                log.error(f'VirtualMachine {virtual_machine.get("metadata").get("name")} not running')
                return False

        log.info("Check virtual machines passed")
        return True
