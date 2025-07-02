import unittest
from unittest.mock import MagicMock, patch

from check_ping import CheckPing
from pydantic import ValidationError


class TestCheckPing(unittest.TestCase):
    def setUp(self):
        # Patch the DistributedRunner to avoid actual k8s calls
        self.mock_distributed_runner_patch = patch("check_ping.DistributedRunner")
        self.MockDistributedRunner = self.mock_distributed_runner_patch.start()
        self.mock_runner_instance = MagicMock()
        self.MockDistributedRunner.return_value = self.mock_runner_instance

        self.valid_params = {
            "pingTarget": "8.8.8.8",
        }

    def tearDown(self):
        self.mock_distributed_runner_patch.stop()

    def test_init_with_minimal_parameters(self):
        """Tests that CheckPing initializes correctly with minimal valid parameters."""
        check = CheckPing(self.valid_params)
        self.assertEqual(check.namespace, "cluster-health")
        self.assertEqual(check.image, "alpine:3.22")
        self.assertEqual(check.count, 1)
        self.assertEqual(check.timeout_seconds, 300)
        self.assertEqual(check.ping_target, "8.8.8.8")
        self.assertIsNone(check.secondary_network_config)
        self.assertIsNone(check.avg_rtt_ms_threshold)
        self.assertIsNone(check.max_rtt_ms_threshold)

    def test_init_with_custom_parameters(self):
        """Tests initialization with custom parameters."""
        params = {
            "namespace": "custom-ns",
            "image": "my-custom/ping:latest",
            "secondaryNetworkConfig": "my-net-config",
            "timeoutSeconds": 120,
            "count": 5,
            "avgRttMsThreshold": 50.0,
            "maxRttMsThreshold": 100.0,
            "pingTarget": "1.1.1.1",
        }
        check = CheckPing(params)
        self.assertEqual(check.namespace, "custom-ns")
        self.assertEqual(check.image, "my-custom/ping:latest")
        self.assertEqual(check.secondary_network_config, "my-net-config")
        self.assertEqual(check.timeout_seconds, 120)
        self.assertEqual(check.count, 5)
        self.assertEqual(check.avg_rtt_ms_threshold, 50.0)
        self.assertEqual(check.max_rtt_ms_threshold, 100.0)
        self.assertEqual(check.ping_target, "1.1.1.1")

    def test_init_with_missing_required_parameters(self):
        """Tests that initialization fails if required parameters are missing."""
        with self.assertRaises(ValidationError):
            CheckPing({"namespace": "test"})  # Missing pingTarget

    # --- Log Parsing Tests ---

    def test_parse_pod_logs_success_no_rtt_check(self):
        """Tests the log parsing function with successful ping results and no RTT checks."""
        check = CheckPing(self.valid_params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = """
        PING 8.8.8.8 (8.8.8.8): 56 data bytes
        64 bytes from 8.8.8.8: seq=0 ttl=118 time=10.5 ms

        --- 8.8.8.8 ping statistics ---
        1 packets transmitted, 1 packets received, 0% packet loss
        """
        self.assertTrue(log_parser(logs, "node-1"))

    def test_parse_pod_logs_success_with_rtt_check_iputils(self):
        """Tests log parsing with successful RTTs (iputils-ping format)."""
        params = self.valid_params.copy()
        params["avgRttMsThreshold"] = 20.0
        params["maxRttMsThreshold"] = 30.0
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = """
        PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
        64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=15.1 ms

        --- 8.8.8.8 ping statistics ---
        1 packets transmitted, 1 received, 0% packet loss, time 0ms
        rtt min/avg/max/mdev = 15.100/15.100/15.100/0.000 ms
        """
        self.assertTrue(log_parser(logs, "node-1"))

    def test_parse_pod_logs_success_with_rtt_check_busybox(self):
        """Tests log parsing with successful RTTs (busybox ping format)."""
        params = self.valid_params.copy()
        params["avgRttMsThreshold"] = 20.0
        params["maxRttMsThreshold"] = 30.0
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = """
        PING 8.8.8.8 (8.8.8.8): 56 data bytes
        64 bytes from 8.8.8.8: seq=0 ttl=118 time=15.1 ms

        --- 8.8.8.8 ping statistics ---
        1 packets transmitted, 1 packets received, 0% packet loss
        round-trip min/avg/max = 15.100/15.100/15.100 ms
        """
        self.assertTrue(log_parser(logs, "node-1"))

    def test_parse_pod_logs_packet_loss_fail(self):
        """Tests log parsing when packet loss is detected."""
        check = CheckPing(self.valid_params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = "2 packets transmitted, 1 packets received, 50% packet loss"
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_packet_loss_parse_error(self):
        """Tests log parsing with malformed packet loss data."""
        check = CheckPing(self.valid_params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = "Some unexpected output without packet loss information."
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_wrong_packet_count(self):
        """Tests log parsing when the transmitted packet count is wrong."""
        params = self.valid_params.copy()
        params["count"] = 5
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = "1 packets transmitted, 1 received, 0% packet loss"
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_avg_rtt_fail(self):
        """Tests log parsing when average RTT is above the threshold."""
        params = self.valid_params.copy()
        params["avgRttMsThreshold"] = 10.0
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = """
        1 packets transmitted, 1 received, 0% packet loss
        rtt min/avg/max/mdev = 15.0/15.0/15.0/0.0 ms
        """
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_max_rtt_fail(self):
        """Tests log parsing when max RTT is above the threshold."""
        params = self.valid_params.copy()
        params["maxRttMsThreshold"] = 20.0
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = """
        1 packets transmitted, 1 received, 0% packet loss
        rtt min/avg/max/mdev = 15.0/18.0/25.0/2.0 ms
        """
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_rtt_parse_error(self):
        """Tests log parsing with malformed RTT data when RTT check is enabled."""
        params = self.valid_params.copy()
        params["avgRttMsThreshold"] = 10.0
        check = CheckPing(params)
        log_parser = check.parse_pod_logs_from_ping_test_func()
        logs = "1 packets transmitted, 1 received, 0% packet loss. No RTT data."
        self.assertFalse(log_parser(logs, "node-1"))

    # --- is_healthy Tests ---

    def test_is_healthy_success(self):
        """Tests is_healthy when the distributed run is successful."""
        self.mock_runner_instance.run_on_all_nodes.return_value = True
        check = CheckPing(self.valid_params)
        self.assertTrue(check.is_healthy())
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()

    def test_is_healthy_failure(self):
        """Tests is_healthy when the distributed run fails."""
        self.mock_runner_instance.run_on_all_nodes.return_value = False
        check = CheckPing(self.valid_params)
        self.assertFalse(check.is_healthy())
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()

    def test_is_healthy_constructs_runner_correctly(self):
        """Tests that DistributedRunner is constructed with the correct pod template."""
        params = {
            "pingTarget": "8.8.8.8",
            "count": 5,
            "namespace": "ping-ns",
            "timeoutSeconds": 99,
        }
        check = CheckPing(params)
        check.is_healthy()

        self.MockDistributedRunner.assert_called_once()
        _, kwargs = self.MockDistributedRunner.call_args

        self.assertEqual(kwargs["pod_name_prefix"], "ping")
        self.assertEqual(kwargs["namespace"], "ping-ns")
        self.assertEqual(kwargs["timeout_seconds"], 99)
        self.assertIsNotNone(kwargs["log_parse_function"])

        pod_template = kwargs["pod_template"]
        container = pod_template.spec.containers[0]
        self.assertEqual(container.image, "alpine:3.22")
        self.assertEqual(container.command, ["ping", "-c", "5", "8.8.8.8"])
        self.assertIsNone(pod_template.metadata.annotations)

    def test_is_healthy_with_secondary_network(self):
        """Tests that the pod template includes secondary network annotations."""
        params = self.valid_params.copy()
        params["secondaryNetworkConfig"] = '{"name": "net1"}'
        check = CheckPing(params)
        check.is_healthy()

        _, kwargs = self.MockDistributedRunner.call_args
        pod_template = kwargs["pod_template"]
        self.assertEqual(
            pod_template.metadata.annotations,
            {"networking.gke.io/interfaces": '{"name": "net1"}'},
        )


if __name__ == "__main__":
    unittest.main()