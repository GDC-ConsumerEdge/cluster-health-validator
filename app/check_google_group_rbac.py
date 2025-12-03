import logging

from kubernetes import client
from prometheus_client import Counter

log = logging.getLogger("check.googlegrouprbac")

GOOGLE_GROUP_RBAC_SUCCESS_TOTAL = Counter(
    'google_group_rbac_success_total',
    'Total number of successful Google Group RBAC checks'
)
GOOGLE_GROUP_RBAC_FAILURE_TOTAL = Counter(
    'google_group_rbac_failure_total',
    'Total number of failed Google Group RBAC checks'
)


class CheckGoogleGroupRBAC:
    def is_healthy(self):
        try:
            k8s = client.CustomObjectsApi()
            resp = k8s.list_cluster_custom_object(
                group="authentication.gke.io",
                version="v2alpha1",
                plural="clientconfigs",
            )
        except Exception as err:
            log.error("An error occurred fetching the clientconfig %s", err)
            GOOGLE_GROUP_RBAC_FAILURE_TOTAL.inc()
            return False

        try:
            clientconfig = resp.get("items")[0]

            if clientconfig.get("metadata").get("name") != "default" and clientconfig.get("namespace") != "kube-public":
                log.error("Did not find expected default.kube-public clientconfig object")
                GOOGLE_GROUP_RBAC_FAILURE_TOTAL.inc()
                return False

            if clientconfig.get("spec").get("authentication") is None:
                log.error("No authentication methods found in default.kube-public clientconfig object")
                GOOGLE_GROUP_RBAC_FAILURE_TOTAL.inc()
                return False

            for auth in clientconfig.get("spec").get("authentication"):
                if auth.get("name") == "google-authentication-method":
                    log.info("Check Google Group RBAC passed")
                    GOOGLE_GROUP_RBAC_SUCCESS_TOTAL.inc()
                    return True

        except Exception as err:
            log.error("An error occurred parsing the clientconfig %s", err)

        log.info("Check GoogleGroupRBAC failed")
        GOOGLE_GROUP_RBAC_FAILURE_TOTAL.inc()
        return False
