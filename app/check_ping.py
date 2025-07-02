import logging
import re

from kubernetes import client
from pydantic import BaseModel, Field

from distributed_runner import DistributedRunner

log = logging.getLogger("check.ping")

default_image = "alpine:3.22"


class CheckPingParameters(BaseModel):
    namespace: str = "cluster-health"
    image: str = default_image
    secondary_network_config: str = Field(None, alias="secondaryNetworkConfig")
    timeout_seconds: int = Field(300, alias="timeoutSeconds")
    count: int = 1
    avg_rtt_ms_threshold: float = Field(None, alias="avgRttMsThreshold")
    max_rtt_ms_threshold: float = Field(None, alias="maxRttMsThreshold")
    ping_target: str = Field(alias="pingTarget")


class CheckPing:
    """
    Runs a network ping test on each node in the cluster.
    The check creates a Pod that runs on each node one at a time. Each pod
    executes 'ping', and the results are read from the pod logs.
    The packet loss and round-trip times are then checked. The Pod is
    cleaned up after the check.
    """

    def __init__(self, parameters: dict) -> None:
        params = CheckPingParameters(**parameters)
        self.namespace = params.namespace
        self.secondary_network_config = params.secondary_network_config
        self.image = params.image
        self.count = params.count
        self.timeout_seconds = params.timeout_seconds
        self.avg_rtt_ms_threshold = params.avg_rtt_ms_threshold
        self.max_rtt_ms_threshold = params.max_rtt_ms_threshold
        self.ping_target = params.ping_target
        self.k8s_core_v1 = client.CoreV1Api()
        self.k8s_apps_v1 = client.AppsV1Api()

    def parse_pod_logs_from_ping_test_func(self) -> callable:
        """
        Creates a parsing function that reads log output from each pod and assesses health check pass/fail.
        """
        count = self.count
        avg_rtt_ms_threshold = self.avg_rtt_ms_threshold
        max_rtt_ms_threshold = self.max_rtt_ms_threshold

        def parse_pod_logs_from_ping_test(logs: str, node_name: str) -> bool:
            # Check for 0% packet loss
            packet_loss_match = re.search(r"(\d+)% packet loss", logs)
            if not packet_loss_match:
                log.error(
                    f"Could not parse packet loss from ping results on node {node_name}. Logs:\n{logs}"
                )
                return False

            packet_loss = int(packet_loss_match.group(1))
            if packet_loss > 0:
                log.error(f"Node {node_name}: {packet_loss}% packet loss detected.")
                return False

            # Check if the correct number of packets were transmitted and received
            transmitted_match = re.search(r"(\d+) packets transmitted", logs)
            if not transmitted_match:
                log.error(
                    f"Could not parse transmitted packets on node {node_name}. Logs:\n{logs}"
                )
                return False

            transmitted = int(transmitted_match.group(1))
            if transmitted != count:
                log.error(
                    f"Node {node_name}: Expected {count} packets transmitted, but got {transmitted}."
                )
                return False

            # If RTT checks are configured, parse and validate them.
            if avg_rtt_ms_threshold is not None or max_rtt_ms_threshold is not None:
                # Regex for iputils-ping: rtt min/avg/max/mdev = 0.052/0.052/0.052/0.000 ms
                rtt_match = re.search(
                    r"rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/([\d\.]+)/[\d\.]+ ms", logs
                )
                if not rtt_match:
                    # Fallback for busybox ping: round-trip min/avg/max = 0.052/0.052/0.052 ms
                    rtt_match = re.search(
                        r"round-trip min/avg/max = [\d\.]+/([\d\.]+)/([\d\.]+) ms", logs
                    )

                if not rtt_match:
                    log.error(
                        f"Could not parse RTT from ping results on node {node_name} but RTT checks were requested. Logs:\n{logs}"
                    )
                    return False

                rtt_avg = float(rtt_match.group(1))
                rtt_max = float(rtt_match.group(2))
                log.info(
                    f"Node {node_name}: Ping RTT avg={rtt_avg:.2f}ms, max={rtt_max:.2f}ms"
                )

                if avg_rtt_ms_threshold is not None and rtt_avg > avg_rtt_ms_threshold:
                    log.error(
                        f"Node {node_name} average RTT {rtt_avg:.2f}ms is above maximum of {avg_rtt_ms_threshold}ms."
                    )
                    return False

                if max_rtt_ms_threshold is not None and rtt_max > max_rtt_ms_threshold:
                    log.error(
                        f"Node {node_name} max RTT {rtt_max:.2f}ms is above maximum of {max_rtt_ms_threshold}ms."
                    )
                    return False

            log.info(f"Node {node_name}: Ping test successful with 0% packet loss.")
            return True

        return parse_pod_logs_from_ping_test

    def is_healthy(self):
        command_args = ["ping", "-c", str(self.count), self.ping_target]

        container = client.V1Container(
            name="ping-container",
            image=self.image,
            command=command_args,
        )

        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            termination_grace_period_seconds=5,
        )

        metadata = client.V1ObjectMeta(
            labels={"app": "ping-test"},
        )

        if self.secondary_network_config:
            metadata.annotations = {
                "networking.gke.io/interfaces": self.secondary_network_config
            }

        template = client.V1PodTemplateSpec(
            metadata=metadata,
            spec=pod_spec,
        )

        runner = DistributedRunner(
            pod_name_prefix="ping",
            namespace=self.namespace,
            pod_template=template,
            timeout_seconds=self.timeout_seconds,
            log_parse_function=self.parse_pod_logs_from_ping_test_func(),
        )

        return runner.run_on_all_nodes()
