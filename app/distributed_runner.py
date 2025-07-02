import logging
import time
import copy
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from typing import Callable

log = logging.getLogger("DistributedRunner")


class DistributedRunner:
    """
    A helper class to run commands within Pods on Kubernetes nodes.
    It handles pod creation, waiting for completion, log retrieval, and cleanup.

    Args:
    pod_name_prefix: A string prefix for the name of the pods that will be
        created.
    namespace: The Kubernetes namespace in which to create the pods.
    pod_template: A V1PodTemplateSpec object that defines the pod to be
        created on each node. The runner will use this template to create
        a pod and schedule it on a specific node.
    timeout_seconds: The maximum time in seconds to wait for a pod to
        complete its execution.
    log_parse_function: A callable that processes the logs of a completed
        pod. It should accept two arguments: the log string and the node
        name, and return a boolean indicating whether the check passed.

    """

    def __init__(
        self,
        pod_name_prefix: str,
        namespace: str,
        pod_template: client.V1PodTemplateSpec,
        timeout_seconds: int,
        log_parse_function: Callable[[str, str], bool],
    ):
        self.pod_name_prefix = pod_name_prefix
        self.namespace = namespace
        self.pod_template = pod_template
        self.timeout_seconds = timeout_seconds
        self.log_parse_function = log_parse_function
        self.k8s_core_v1 = client.CoreV1Api()

    def _get_nodes_on_cluster(self):
        nodes = self.k8s_core_v1.list_node()
        return [node.metadata.name for node in nodes.items]

    def _get_pod_name_for_node(self, node_name):
        return f"{self.pod_name_prefix}-{node_name}"

    def _create_pod_on_node(self, node_name):
        pod_name = self._get_pod_name_for_node(node_name)

        # Deepcopy the spec to avoid modifying the original template in-place.
        pod_spec = copy.deepcopy(self.pod_template.spec)
        pod_spec.node_name = node_name  # Schedule the pod on the specific node.

        pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels=self.pod_template.metadata.labels,
            ),
            spec=pod_spec,
        )

        try:
            self.k8s_core_v1.create_namespaced_pod(namespace=self.namespace, body=pod)

            log.info(f"Pod {pod_name} created on node {node_name} in namespace {self.namespace}")
        except ApiException as e:
            log.error(
                f"Failed to create Pod {pod_name} on node {node_name}: {e}"
            )
            raise

    def _wait_for_pod_to_complete(self, node_name):
        pod_name = self._get_pod_name_for_node(node_name)

        start_time = time.time()
        while time.time() - start_time < self.timeout_seconds:
            try:
                pod = self.k8s_core_v1.read_namespaced_pod(
                    namespace=self.namespace,
                    name=pod_name,
                )
            except ApiException as e:
                log.error(f"Error reading pod: {e}")
                return False

            if pod.status.phase == "Succeeded":
                return True
            elif pod.status.phase in ["Failed", "Unknown"]:
                log.error(f"Pod {pod_name} on node {pod.spec.node_name} failed.")
                return False

            log.info(f"Waiting for pod {pod_name} to complete...")
            time.sleep(10)
        log.error("Timeout waiting for pods to complete.")
        return False

    def _get_pod_logs_and_parse(self, node_name):
        pod_name = self._get_pod_name_for_node(node_name)

        log.info(f"Fetching logs for pod {pod_name} on node {node_name}")
        try:
            logs = self.k8s_core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
            )
            return self.log_parse_function(logs, node_name)
        except ApiException as e:
            log.error(f"Error reading logs for pod {pod_name} on node {node_name}: {e}")
            return False

    def _cleanup(self, node):
        pod_name = self._get_pod_name_for_node(node)

        try:
            self.k8s_core_v1.delete_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
            log.info(f"Pod {pod_name} is deleted.")
        except ApiException as e:
            if e.status == 404:
                log.info(
                    f"Pod {pod_name} was not found for cleanup, might have been deleted already or failed to create."
                )
            else:
                log.error(f"Failed to delete Pod {pod_name}: {e}")

    def run_on_all_nodes(self):
        overall_success = True

        for node in self._get_nodes_on_cluster():
            node_success = True
            try:
                log.info(f"--- Running on node: {node} ---")
                self._create_pod_on_node(node)

                # A small delay to allow the pod to be scheduled.
                time.sleep(5)

                if not self._wait_for_pod_to_complete(node):
                    log.error(f"Pod on node {node} did not complete successfully.")
                    node_success = False

                if node_success and not self._get_pod_logs_and_parse(node):
                    log.error(f"Check failed on node {node} after parsing logs.")
                    node_success = False
                elif node_success:
                    log.info(f"Check passed on node {node}.")

            except Exception as e:
                log.error(
                    f"An unexpected error occurred during execution on node {node}: {e}",
                    exc_info=True,
                )
                node_success = False
            finally:
                log.info(f"--- Cleaning up for node: {node} ---")
                self._cleanup(node)
            if not node_success:
                overall_success = False

        return overall_success
