import unittest
from unittest.mock import MagicMock, patch

from kubernetes.client.exceptions import ApiException

from distributed_runner import DistributedRunner
from kubernetes import client


class TestDistributedRunner(unittest.TestCase):
    def setUp(self):
        self.mock_core_v1_api_patch = patch("kubernetes.client.CoreV1Api")
        self.MockCoreV1Api = self.mock_core_v1_api_patch.start()
        self.mock_core_v1_instance = MagicMock()
        self.MockCoreV1Api.return_value = self.mock_core_v1_instance

        self.mock_time_patch = patch("time.sleep")
        self.mock_time = self.mock_time_patch.start()

        self.mock_log_parse_function = MagicMock()

        self.pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": "test"}),
            spec=client.V1PodSpec(
                containers=[client.V1Container(name="test-container")],
                restart_policy="Never",
            ),
        )

        self.runner = DistributedRunner(
            pod_name_prefix="test-pod",
            namespace="test-ns",
            pod_template=self.pod_template,
            timeout_seconds=60,
            log_parse_function=self.mock_log_parse_function,
        )

    def tearDown(self):
        self.mock_core_v1_api_patch.stop()
        self.mock_time_patch.stop()

    def _mock_node_list(self, node_names):
        nodes = [
            client.V1Node(metadata=client.V1ObjectMeta(name=name))
            for name in node_names
        ]
        self.mock_core_v1_instance.list_node.return_value = client.V1NodeList(
            items=nodes
        )

    def test_run_on_all_nodes_success(self):
        """Tests run_on_all_nodes when all nodes succeed."""
        self._mock_node_list(["node-1", "node-2"])
        self.mock_log_parse_function.return_value = True

        # Mock pod status flow
        pod_succeeded = MagicMock()
        pod_succeeded.status.phase = "Succeeded"
        self.mock_core_v1_instance.read_namespaced_pod.return_value = pod_succeeded
        self.mock_core_v1_instance.read_namespaced_pod_log.return_value = "Success log"

        result = self.runner.run_on_all_nodes()

        self.assertTrue(result)
        self.assertEqual(self.mock_core_v1_instance.create_namespaced_pod.call_count, 2)
        self.assertEqual(self.mock_core_v1_instance.delete_namespaced_pod.call_count, 2)
        self.assertEqual(self.mock_log_parse_function.call_count, 2)

    def test_run_on_all_nodes_one_fails(self):
        """Tests run_on_all_nodes when one node's check fails."""
        self._mock_node_list(["node-1", "node-2"])
        # First call fails, second succeeds
        self.mock_log_parse_function.side_effect = [False, True]

        pod_succeeded = MagicMock()
        pod_succeeded.status.phase = "Succeeded"
        self.mock_core_v1_instance.read_namespaced_pod.return_value = pod_succeeded
        self.mock_core_v1_instance.read_namespaced_pod_log.return_value = "log"

        result = self.runner.run_on_all_nodes()

        self.assertFalse(result)
        # Should still try to run on and clean up both nodes
        self.assertEqual(self.mock_core_v1_instance.create_namespaced_pod.call_count, 2)
        self.assertEqual(self.mock_core_v1_instance.delete_namespaced_pod.call_count, 2)
        self.assertEqual(self.mock_log_parse_function.call_count, 2)

    def test_run_on_all_nodes_pod_wait_fails(self):
        """Tests run_on_all_nodes when a pod fails to complete."""
        self._mock_node_list(["node-1"])

        pod_failed = MagicMock()
        pod_failed.status.phase = "Failed"
        self.mock_core_v1_instance.read_namespaced_pod.return_value = pod_failed

        result = self.runner.run_on_all_nodes()

        self.assertFalse(result)
        self.mock_core_v1_instance.create_namespaced_pod.assert_called_once()
        # Log parsing should not be called if pod wait fails
        self.mock_log_parse_function.assert_not_called()
        self.mock_core_v1_instance.delete_namespaced_pod.assert_called_once()

    def test_run_on_all_nodes_creation_api_error(self):
        """Tests run_on_all_nodes when pod creation fails with an API error."""
        self._mock_node_list(["node-1"])
        self.mock_core_v1_instance.create_namespaced_pod.side_effect = ApiException(
            status=500, reason="Internal Server Error"
        )

        result = self.runner.run_on_all_nodes()

        self.assertFalse(result)
        self.mock_core_v1_instance.create_namespaced_pod.assert_called_once()
        # Cleanup should still be called
        self.mock_core_v1_instance.delete_namespaced_pod.assert_called_once()

    def test_wait_for_pod_to_complete_timeout(self):
        """Tests the timeout logic in _wait_for_pod_to_complete."""
        self.runner.timeout_seconds = 1  # Short timeout for test
        pod_running = MagicMock()
        pod_running.status.phase = "Running"
        self.mock_core_v1_instance.read_namespaced_pod.return_value = pod_running

        # Testing a private method here to isolate the complex wait logic.
        result = self.runner._wait_for_pod_to_complete("node-1")

        self.assertFalse(result)

    def test_cleanup_pod_not_found(self):
        """Tests that cleanup handles 404 errors gracefully."""
        self.mock_core_v1_instance.delete_namespaced_pod.side_effect = ApiException(
            status=404, reason="Not Found"
        )
        try:
            # _cleanup doesn't return anything, just shouldn't raise an unhandled exception
            self.runner._cleanup("node-1")
        except ApiException:
            self.fail("_cleanup() raised ApiException unexpectedly!")

    def test_create_pod_on_node_logic(self):
        """Tests that _create_pod_on_node correctly constructs and creates a pod."""
        node_name = "test-node"
        pod_name = f"{self.runner.pod_name_prefix}-{node_name}"

        self.runner._create_pod_on_node(node_name)

        self.mock_core_v1_instance.create_namespaced_pod.assert_called_once()
        _, kwargs = self.mock_core_v1_instance.create_namespaced_pod.call_args
        created_pod_body = kwargs["body"]

        self.assertIsInstance(created_pod_body, client.V1Pod)
        self.assertEqual(created_pod_body.metadata.name, pod_name)
        self.assertEqual(created_pod_body.metadata.namespace, "test-ns")
        self.assertEqual(created_pod_body.spec.node_name, node_name)
        self.assertEqual(created_pod_body.spec.restart_policy, "Never")