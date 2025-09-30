import logging

from kubernetes import client
from pydantic import BaseModel

log = logging.getLogger("check.virtualmachinedisks")


class CheckVirtualMachineDisksParameters(BaseModel):
    namespace: str
    count: int | None = None


class CheckVirtualMachineDisks:
    def __init__(self, parameters: dict) -> None:
        params = CheckVirtualMachineDisksParameters(**parameters)
        self.namespace = params.namespace
        self.count = params.count

    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(
            group="vm.cluster.gke.io",
            version="v1",
            plural="virtualmachinedisks",
            namespace=self.namespace,
        )
        
        # Check for specified count of virtualmachinedisks
        if self.count is not None and len(resp.get("items")) != self.count:
            log.error(
                f'Found {len(resp.get("items"))} virtualmachinedisks but expected {self.count}.'
            )
            return False
       
        # Assert that each virtualmachine disk is Succeeded.
        for virtual_machine_disk in resp.get("items"):
            if virtual_machine_disk.get("status").get("phase") != "Succeeded":
                log.error(
                    f'DataVolume {virtual_machine_disk.get("metadata").get("name")} phase not succeeded'
                )
                return False
            
            if virtual_machine_disk.get("status").get("progress") != "100.0%" and not virtual_machine_disk.get("metadata").get("labels").get("vm.cluster.gke.io/virtual-machine-restore"):
                log.error(
                    f'DataVolume {virtual_machine_disk.get("metadata").get("name")} not finished importing'
                )
                return False
            

        log.info("Check virtual machines disks passed")
        return True
