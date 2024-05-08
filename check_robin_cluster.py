from kubernetes import client
import logging

log = logging.getLogger('check.robincluster')

class CheckRobinCluster:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_cluster_custom_object(group="manage.robin.io", version="v1", plural="robinclusters")

        failedCheck = False

        if (len(resp.get("items")) != 1):
            log.error(f'Found {len(resp.items)} robinclusters but wanted 1.')
            return failedCheck
        
        # Assert that the overall robincluster status is Ready
        robin_cluster = resp.get("items")[0]

        if (robin_cluster.get("status").get("phase") != "Ready"):
            log.error(f'Robin cluster not ready.')
            return failedCheck
        
        robin_nodes = robin_cluster.get("status").get("robin_node_status")

        if (len(robin_nodes) != 3):
            log.error(f'Found {len(robin_nodes)} robin nodes but wanted 3.')
            return failedCheck

        # Assert that robin_node_status contains 3 nodes and are all ONLINE and Ready
        for node in robin_nodes:
            if node.get("state") != "ONLINE" or node.get("status") != "Ready":
                log.error(f'Robin node ({node.host_name}) not online or ready.')
                return failedCheck

        log.info("Check robin cluster passed")
        return True
