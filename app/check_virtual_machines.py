from kubernetes import client
import logging

log = logging.getLogger('check.virtualmachines')

class CheckVirtualMachines:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(group="vm.cluster.gke.io", version="v1", plural="virtualmachines", namespace="vm-workloads")

        # Expect multiple virtualmachines
        if (len(resp.get("items")) < 2):
            log.error(f'Found {len(resp.get("items"))} virtualmachines but expected 2 or more.')
            return False

        # Assert that each virtualmachine is running
        for virtual_machine in resp.get("items"):
            if (virtual_machine.get("status").get("state") != "Running"):
                log.error(f'VirtualMachine {virtual_machine.get("metadata").get("name")} not running')
                return False

        log.info("Check virtual machines passed")
        return True
