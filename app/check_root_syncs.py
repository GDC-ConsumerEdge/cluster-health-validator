import logging
import pprint

from kubernetes import client

log = logging.getLogger("check.rootsyncs")


class CheckRootSyncs:
    def is_healthy(self):
        # k8s_app = client.AppsV1Api()
        # try:
        #     resp = k8s_app.read_namespaced_deployment(
        #         name="config-management-operator",
        #         namespace="config-management-system",
        #     )
        #     if resp.status.ready_replicas != 1:
        #         log.error(
        #             "deployment.apps/config-management-operator is not running."
        #             + f" Found {resp.status.ready_replicas} ready replicas but expected 1"
        #         )
        #         return False
        # except client.ApiException as e:
        #     log.error(
        #         "Exception when calling AppsV1Api->read_namespaced_deployment: %s\n" % e
        #     )
        #     return False

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
                return False

        log.info("Check root syncs passed")
        return True
