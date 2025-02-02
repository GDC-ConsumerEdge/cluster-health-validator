import logging

from kubernetes import client
from pydantic import BaseModel

log = logging.getLogger("check.datavolumes")


class CheckDataVolumesParameters(BaseModel):
    namespace: str
    count: int


class CheckDataVolumes:
    def __init__(self, parameters: dict) -> None:
        params = CheckDataVolumesParameters(**parameters)

        self.namespace = params.namespace
        self.count = params.count

    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(
            group="cdi.kubevirt.io",
            version="v1beta1",
            plural="datavolumes",
            namespace=self.namespace,
        )

        if len(resp.get("items")) != self.count:
            log.error(
                f'Found {len(resp.get("items"))} datavolumes but expected {self.count}.'
            )
            return False

        # Assert that each data volume is 100% imported and ready
        for data_volume in resp.get("items"):
            if data_volume.get("status").get("phase") != "Succeeded":
                log.error(
                    f'DataVolume {data_volume.get("metadata").get("name")} phase not succeeded'
                )
                return False

            if data_volume.get("status").get("progress") != "100.0%":
                log.error(
                    f'DataVolume {data_volume.get("metadata").get("name")} not imported'
                )
                return False

        log.info("Check data volumes passed")
        return True
