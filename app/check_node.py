from kubernetes import client
import logging

log = logging.getLogger('check.node')

class CheckNode:
    def is_healthy(self):
        k8s = client.CoreV1Api()
        resp = k8s.list_node()

        failedCheck = False

        for node in resp.items:
            nodeReady = False
            for condition in node.status.conditions:
                if (condition.type == 'Ready' and condition.status == 'True'):
                    nodeReady = True

            if (not nodeReady):
                log.error(f"Node {node.metadata.name} is not ready.")
                failedCheck = True

        log.info("Check node passed")
        return not failedCheck
