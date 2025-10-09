from kubernetes import client
import logging
from prometheus_client import Counter

log = logging.getLogger('check.nodes')

NODE_HEALTH_SUCCESS_TOTAL = Counter(
    'node_health_success_total',
    'Total number of successful node health checks'
)
NODE_HEALTH_FAILURE_TOTAL = Counter(
    'node_health_failure_total',
    'Total number of failed node health checks'
)

class CheckNodes:
    def is_healthy(self):
        k8s = client.CoreV1Api()
        resp = k8s.list_node()

        for node in resp.items:
            nodeReady = False
            for condition in node.status.conditions:
                if (condition.type == 'Ready' and condition.status == 'True'):
                    nodeReady = True

            if (not nodeReady):
                log.error(f"Node {node.metadata.name} is not ready.")
                NODE_HEALTH_FAILURE_TOTAL.inc()
                return False

        log.info("Check nodes passed")
        NODE_HEALTH_SUCCESS_TOTAL.inc()
        return True
