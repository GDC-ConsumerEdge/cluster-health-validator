from kubernetes import client
import logging

log = logging.getLogger('check.nodes')

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
                return False

        log.info("Check nodes passed")
        return True
