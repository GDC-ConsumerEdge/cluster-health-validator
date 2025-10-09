import logging
import pprint

from kubernetes import client
from prometheus_client import Counter

log = logging.getLogger("check.rootsyncs")

ROOT_SYNCS_SUCCESS_TOTAL = Counter(
    'root_syncs_success_total',
    'Total number of successful root syncs checks'
)
ROOT_SYNCS_FAILURE_TOTAL = Counter(
    'root_syncs_failure_total',
    'Total number of failed root syncs checks'
)


class CheckRootSyncs:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(
            group="configsync.gke.io",
            version="v1beta1",
            plural="rootsyncs",
            namespace="config-management-system",
        )

        # Expect at least 1 root sync object!
        if len(resp.get("items")) < 1:
            log.error(
                f'Found {len(resp.get("items"))} rootsyncs but expected 1 or more.'
            )
            ROOT_SYNCS_FAILURE_TOTAL.inc()
            return False

        # Assert that each root sync is synced and completed reconciling
        for root_sync in resp.get("items"):
            sync_conditions = root_sync.get("status").get("conditions")
            reconciling_condition = [
                condition
                for condition in sync_conditions
                if condition.get("type") == "Reconciling"
            ][0]
            if reconciling_condition.get("status") != "False":
                log.error(f'RootSync {root_sync.get("name")} is still reconciling')
                ROOT_SYNCS_FAILURE_TOTAL.inc()
                return False

            syncing_condition = [
                condition
                for condition in sync_conditions
                if condition.get("type") == "Syncing"
            ][0]
            if (
                syncing_condition.get("status") != "False"
                or syncing_condition.get("message") != "Sync Completed"
            ):
                log.error(
                    f'RootSync {root_sync.get("metadata").get("name")} syncing not complete'
                )
                ROOT_SYNCS_FAILURE_TOTAL.inc()
                return False

        log.info("Check root syncs passed")
        ROOT_SYNCS_SUCCESS_TOTAL.inc()
        return True
