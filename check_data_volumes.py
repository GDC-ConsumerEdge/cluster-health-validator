from kubernetes import client
import logging

log = logging.getLogger('check.datavolumes')

class CheckDataVolumes:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(group="cdi.kubevirt.io", version="v1beta1", plural="datavolumes", namespace="vm-workloads")

        failedCheck = False

        # Expect multiple datavolumes
        if (len(resp.get("items")) < 2):
            log.error(f'Found {len(resp.items)} rootsyncs but expected 1 or more.')
            return failedCheck
        
        # Assert that each data volume is 100% imported and ready
        for data_volume in resp.get("items"):
            if (data_volume.get("status").get("phase") != "Succeeded"):
                log.error(f'DataVolume {data_volume.get("metadata").get("name")} phase not succeeded')
                return failedCheck

            if (data_volume.get("status").get("progress") != "100.0%"):
                log.error(f'DataVolume {data_volume.get("metadata").get("name")} not imported')
                return failedCheck

        log.info("Check data volumes passed")
        return True
