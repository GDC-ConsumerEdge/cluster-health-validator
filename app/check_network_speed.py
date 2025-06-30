import logging
import re

from kubernetes import client
from pydantic import BaseModel, Field

from distributed_runner import DistributedRunner

log = logging.getLogger("check.nodespeed")

default_image = "python:3-alpine"


class CheckNodeSpeedParameters(BaseModel):
    namespace: str = "cluster-health"
    min_download_mbps: float = Field(alias="minDownloadMbps")
    min_upload_mbps: float = Field(alias="minUploadMbps")
    image: str = default_image
    timeout_seconds: int = Field(300, alias="timeoutSeconds")


class CheckNodeSpeed:
    """
    Runs a network speed test on each node in the cluster.
    The check creates a Pod that runs on each node one at a time. Each pod
    executes 'speedtest-cli --secure', and the results are read from the pod logs.
    The download and upload speeds are then compared against user-defined
    minimums. The Pod is cleaned up after the check.
    """

    def __init__(self, parameters: dict) -> None:
        params = CheckNodeSpeedParameters(**parameters)
        self.namespace = params.namespace
        self.min_download_mbps = params.min_download_mbps
        self.min_upload_mbps = params.min_upload_mbps
        self.image = params.image
        self.timeout_seconds = params.timeout_seconds
        self.k8s_core_v1 = client.CoreV1Api()
        self.k8s_apps_v1 = client.AppsV1Api()

    """
    Creates a parsing function that reads log output from each pod and assesses health check pass/fail.
    """

    def parse_pod_logs_from_speed_test_func(self) -> callable:
        min_download_mbps = self.min_download_mbps
        min_upload_mbps = self.min_upload_mbps

        def parse_pod_logs_from_speed_test(logs: str, node_name: str) -> bool:
            download_match = re.search(r"Download: ([\d\.]+) Mbit/s", logs)
            upload_match = re.search(r"Upload: ([\d\.]+) Mbit/s", logs)

            if not download_match or not upload_match:
                log.error(
                    f"Could not parse speed test results on node {node_name}. Logs:\n{logs}"
                )
                return False

            download_speed = float(download_match.group(1))
            upload_speed = float(upload_match.group(1))

            log.info(
                f"Node {node_name}: Download={download_speed:.2f} Mbps, Upload={upload_speed:.2f} Mbps"
            )

            if download_speed < min_download_mbps:
                log.error(
                    f"Node {node_name} download speed {download_speed:.2f} Mbps is below minimum of {min_download_mbps} Mbps."
                )
                return False

            if upload_speed < min_upload_mbps:
                log.error(
                    f"Node {node_name} upload speed {upload_speed:.2f} Mbps is below minimum of {min_upload_mbps} Mbps."
                )
                return False

            return True

        return parse_pod_logs_from_speed_test
        ...

    def is_healthy(self):
        if self.image == default_image:
            container = client.V1Container(
                name="speedtest-container",
                image=self.image,
                command=["sh", "-c"],
                args=[
                    "apk update && pip3 install speedtest-cli && speedtest-cli --secure"
                ],
            )
        else:
            container = client.V1Container(
                name="speedtest-container",
                image=self.image,
            )

        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            termination_grace_period_seconds=5,
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"app": "speed-test"}, namespace=self.namespace
            ),
            spec=pod_spec,
        )

        runner = DistributedRunner(
            pod_name_prefix="speedtest",
            namespace=self.namespace,
            pod_template=template,
            timeout_seconds=self.timeout_seconds,
            log_parse_function=self.parse_pod_logs_from_speed_test_func(),
        )

        return runner.run_on_all_nodes()
