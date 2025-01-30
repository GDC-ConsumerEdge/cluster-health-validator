import time
import unittest
from unittest.mock import patch

from health_checks import HealthCheck
from kubernetes.client.rest import ApiException


class TestHealthCheck(unittest.TestCase):

    def setUp(self) -> None:
        self.crd_read_patcher = patch(
            "kubernetes.client.ApiextensionsV1Api.read_custom_resource_definition"
        )
        self.crd_create_patcher = patch(
            "kubernetes.client.ApiextensionsV1Api.create_custom_resource_definition"
        )
        self.custom_get_patcher = patch(
            "kubernetes.client.CustomObjectsApi.get_cluster_custom_object"
        )
        self.custom_create_patcher = patch(
            "kubernetes.client.CustomObjectsApi.create_cluster_custom_object"
        )
        self.custom_patch_patcher = patch(
            "kubernetes.client.CustomObjectsApi.patch_cluster_custom_object_status"
        )
        self.load_config_patcher = patch("kubernetes.config.load_config")
        self.crd_read = self.crd_read_patcher.start()
        self.crd_create = self.crd_create_patcher.start()
        self.custom_get = self.custom_get_patcher.start()
        self.custom_create = self.custom_create_patcher.start()
        self.custom_patch = self.custom_patch_patcher.start()
        self.load_config_patcher.start()
        # default healthcheck with mocks for all k8s ops
        self.hc = HealthCheck()

    def tearDown(self) -> None:
        patch.stopall()

    def test_is_crd_installed(self):
        self.crd_read.side_effect = [ApiException(status=404), True]
        self.assertFalse(self.hc.is_crd_installed())
        self.assertTrue(self.hc.is_crd_installed())

    def test_is_resource_present(self):
        self.custom_get.side_effect = [ApiException(status=404), True]
        self.assertFalse(self.hc.is_resource_present())
        self.assertTrue(self.hc.is_resource_present())

    def test_create(self):
        self.hc.create()
        self.custom_create.assert_called_once()
        self.custom_patch.assert_called_once()

    def test_init_no_crd_no_cr(self):
        self.crd_read.side_effect = [ApiException(status=404), True]
        self.custom_get.side_effect = ApiException(status=404)
        _ = HealthCheck()
        self.crd_create.assert_called_once()
        self.custom_create.assert_called_once()

    def test_init_crd_no_cr(self):
        self.custom_get.side_effect = ApiException(status=404)
        _ = HealthCheck()
        self.crd_create.assert_not_called()
        self.custom_create.assert_called_once()

    def test_update_condition(self):
        # Condition with failed checks
        condition = HealthCheck.HealthCheckCondition(
            type="PlatformHealthy",
            status="Unknown",
            reason="Pending",
            message="Checks not run yet",
        )
        failed_checks = ["Check1", "Check2"]
        self.hc.update_condition(condition, failed_checks)
        self.assertEqual(condition.status, "False")
        self.assertEqual(condition.reason, "HealthChecksFailed")
        self.assertEqual(condition.message, "Failed checks: Check1,Check2")

        # lasttransition time should not change on the same state
        lastTransitionTime = condition.lastTransitionTime
        self.hc.update_condition(condition, failed_checks)
        self.assertEqual(
            condition.lastTransitionTime,
            lastTransitionTime,
            "lastTransitionTime should not change if the condition is same",
        )

        # Condition with passed checks
        failed_checks = []
        lastTransitionTime = condition.lastTransitionTime
        time.sleep(1)  # to verify the lastTransitionTime changes
        self.hc.update_condition(condition, failed_checks)
        self.assertEqual(condition.status, "True")
        self.assertEqual(condition.reason, "HealthChecksPassed")
        self.assertEqual(condition.message, "")
        self.assertNotEqual(
            condition.lastTransitionTime,
            lastTransitionTime,
            "lastTransitionTime should change if the condition is different",
        )

    def test_update_status(self):
        failed_checks = ["Check1", "Check2"]
        expected_condition_platform_no_failedchecks = HealthCheck.HealthCheckCondition(
            type="PlatformHealthy",
            status="True",
            reason="HealthChecksPassed",
            message="",
        )
        expected_condition_platform_failedchecks = HealthCheck.HealthCheckCondition(
            type="PlatformHealthy",
            status="False",
            reason="HealthChecksFailed",
            message="Failed checks: " + ",".join(failed_checks),
        )
        expected_condition_workloads_no_failedchecks = HealthCheck.HealthCheckCondition(
            type="WorkloadsHealthy",
            status="True",
            reason="HealthChecksPassed",
            message="",
        )
        expected_condition_workloads_failedchecks = HealthCheck.HealthCheckCondition(
            type="WorkloadsHealthy",
            status="False",
            reason="HealthChecksFailed",
            message="Failed checks: " + ",".join(failed_checks),
        )

        self.hc.update_status([], [])
        _, kwargs = self.custom_patch.call_args
        self.assertEqual(
            expected_condition_platform_no_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][0]
            ),
        )
        self.assertEqual(
            expected_condition_workloads_no_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][1]
            ),
        )

        self.hc.update_status([], failed_checks)
        _, kwargs = self.custom_patch.call_args
        self.assertEqual(
            expected_condition_platform_no_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][0]
            ),
        )
        self.assertEqual(
            expected_condition_workloads_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][1]
            ),
        )

        self.hc.update_status(failed_checks, [])
        _, kwargs = self.custom_patch.call_args
        self.assertEqual(
            expected_condition_platform_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][0]
            ),
        )
        self.assertEqual(
            expected_condition_workloads_no_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][1]
            ),
        )

        self.hc.update_status(failed_checks, failed_checks)
        _, kwargs = self.custom_patch.call_args
        self.assertEqual(
            expected_condition_platform_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][0]
            ),
        )
        self.assertEqual(
            expected_condition_workloads_failedchecks,
            HealthCheck.HealthCheckCondition(
                **kwargs["body"]["status"]["conditions"][1]
            ),
        )


if __name__ == "__main__":
    unittest.main()
