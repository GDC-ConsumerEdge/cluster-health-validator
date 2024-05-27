from kubernetes import client
import logging

log = logging.getLogger('check.vmruntime')

class CheckVMRuntime:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_cluster_custom_object(group="vm.cluster.gke.io", version="v1", plural="vmruntimes")

        failedCheck = False

        if (len(resp.get("items")) != 1):
            log.error(f'Found {len(resp.get("items"))} vmruntime but wanted 1.')
            return failedCheck
        
        # Assert that the overall vmruntime status is Ready
        vmruntime = resp.get("items")[0]

        if (vmruntime.get("status").get("ready") != True):
            log.error(f'VMRuntime is not ready.')
            return failedCheck
        
        featureStatuses =  vmruntime.get("status").get("preflightCheckSummary").get("featureStatuses")

        for feature in ["CPU", "KVM", "VSOCK"]:
            if (featureStatuses.get(feature).get("passed") != True):
                log.error(f'{feature} preflight check failed.')
                return failedCheck

        log.info("Check vmruntime passed")
        return True
