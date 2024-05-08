from kubernetes import client
import logging

log = logging.getLogger('check.virtualmachines')

class CheckVirtualMachines:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(group="kubevirt.io", version="v1", plural="virtualmachines", namespace="vm-workloads")

        failedCheck = False

        # Expect multiple virtualmachines
        if (len(resp.get("items")) < 2):
            log.error(f'Found {len(resp.items)} virtualmachines but expected 2 or more.')
            return failedCheck
        
        # Assert that each virtualmachine is ready
        for virtual_machine in resp.get("items"):
            if (virtual_machine.get("status").get("created") != True):
                log.error(f'VirtualMachine {virtual_machine.get("metadata").get("name")} not created')
                return failedCheck

            if (virtual_machine.get("status").get("ready") != True):
                log.error(f'VirtualMachine {virtual_machine.get("metadata").get("name")} not ready')
                return failedCheck

            if (virtual_machine.get("status").get("printableStatus") != "Running"):
                log.error(f'VirtualMachine {virtual_machine.get("metadata").get("name")} not running')
                return failedCheck

        log.info("Check virtual machines passed")
        return True
