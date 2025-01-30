import logging

from kubernetes import client

log = logging.getLogger("check.googlegrouprbac")


class CheckGoogleGroupRBAC:
    def is_healthy(self):
        k8s = client.CustomObjectsApi()
        resp = k8s.list_namespaced_custom_object(
            group="authentication.gke.io",
            version="v2alpha1",
            plural="clientconfigs",
            namespace="kube-public",
        )

        try:
            clientconfig = resp.get("items")[0]

            if clientconfig.get("metadata").get("name") != "default":
                log.error(
                    "Did not find expected default.kube-public clientconfig object"
                )
                return False

            for auth in clientconfig.get("spec").get("authentication"):
                if auth.get("name") == "google-authentication-method":
                    log.info("Check Google Group RBAC passed")
                    return True

        except Exception as err:
            log.error("An error occurred parsing the clientconfig %s", err)

        log.info("Check GoogleGroupRBAC failed")
        return False
