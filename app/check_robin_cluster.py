import logging

from kubernetes import client
from prometheus_client import Counter

log = logging.getLogger("check.robincluster")

ROBIN_CLUSTER_SUCCESS_TOTAL = Counter(
    'robin_cluster_success_total',
    'Total number of successful Robin cluster checks'
)
ROBIN_CLUSTER_FAILURE_TOTAL = Counter(
    'robin_cluster_failure_total',
    'Total number of failed Robin cluster checks'
)


class CheckRobinCluster:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_cluster_custom_object(
            group="manage.robin.io", version="v1", plural="robinclusters"
        )

        if len(resp.get("items")) != 1:
            log.error(f'Found {len(resp.get("items"))} robinclusters but wanted 1.')
            ROBIN_CLUSTER_FAILURE_TOTAL.inc()
            return False

        # Assert that the overall robincluster status is Ready
        robin_cluster = resp.get("items")[0]

        if robin_cluster.get("status").get("phase") != "Ready":
            log.error("Robin cluster not ready.")
            ROBIN_CLUSTER_FAILURE_TOTAL.inc()
            return False

        robin_nodes = robin_cluster.get("status").get("robin_node_status")

        if len(robin_nodes) != 3:
            log.error(f"Found {len(robin_nodes)} robin nodes but wanted 3.")
            ROBIN_CLUSTER_FAILURE_TOTAL.inc()
            return False

        # Assert that robin_node_status contains 3 nodes and are all ONLINE and Ready
        for node in robin_nodes:
            if node.get("state") != "ONLINE" or node.get("status") != "Ready":
                log.error(f"Robin node ({node.host_name}) not online or ready.")
                ROBIN_CLUSTER_FAILURE_TOTAL.inc()
                return False

        log.info("Check robin cluster passed")
        ROBIN_CLUSTER_SUCCESS_TOTAL.inc()
        return True
