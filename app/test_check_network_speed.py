import unittest
from unittest.mock import MagicMock, patch

from check_network_speed import CheckNetworkSpeed
from kubernetes import client
from pydantic import ValidationError


class TestCheckNodeSpeed(unittest.TestCase):
    def setUp(self):
        # Patch the DistributedRunner to avoid actual k8s calls
        self.mock_distributed_runner_patch = patch(
            "check_network_speed.DistributedRunner"
        )
        self.MockDistributedRunner = self.mock_distributed_runner_patch.start()
        self.mock_runner_instance = MagicMock()
        self.MockDistributedRunner.return_value = self.mock_runner_instance

        self.mock_time_patch = patch("utils.time.time")
        self.mock_time = self.mock_time_patch.start()

        self.valid_params = {
            "minDownloadMbps": 100.0,
            "minUploadMbps": 50.0,
        }

    def tearDown(self):
        self.mock_distributed_runner_patch.stop()
        self.mock_time_patch.stop()

    def test_init_with_valid_parameters(self):
        """Tests that CheckNodeSpeed initializes correctly with valid parameters."""
        check = CheckNetworkSpeed(self.valid_params)
        self.assertEqual(check.namespace, "cluster-health")  # Default
        self.assertEqual(check.min_download_mbps, 100.0)
        self.assertEqual(check.min_upload_mbps, 50.0)
        self.assertEqual(check.timeout_seconds, 300)  # Default
        self.assertEqual(check.image, "python:3-alpine")  # Default
        self.assertEqual(check.interval_seconds, 0)  # Default

    def test_init_with_custom_parameters(self):
        """Tests initialization with custom parameters."""
        params = {
            "namespace": "custom-ns",
            "minDownloadMbps": 200.0,
            "minUploadMbps": 75.0,
            "image": "my-custom/speedtest:latest",
            "timeoutSeconds": 120,
            "intervalSeconds": 86400,
        }
        check = CheckNetworkSpeed(params)
        self.assertEqual(check.namespace, "custom-ns")
        self.assertEqual(check.min_download_mbps, 200.0)
        self.assertEqual(check.min_upload_mbps, 75.0)
        self.assertEqual(check.image, "my-custom/speedtest:latest")
        self.assertEqual(check.timeout_seconds, 120)
        self.assertEqual(check.interval_seconds, 86400)

    def test_init_with_missing_required_parameters(self):
        """Tests that initialization fails if required parameters are missing."""
        with self.assertRaises(ValidationError):
            CheckNetworkSpeed({"namespace": "test"})  # Missing min speeds

    def test_parse_pod_logs_success(self):
        """Tests the log parsing function with successful speed test results."""
        check = CheckNetworkSpeed(self.valid_params)
        log_parser = check.parse_pod_logs_from_speed_test_func()
        logs = "Ping: 10.5 ms\nDownload: 150.75 Mbit/s\nUpload: 80.20 Mbit/s"
        self.assertTrue(log_parser(logs, "node-1"))

    def test_parse_pod_logs_download_fail(self):
        """Tests the log parsing function when download speed is below minimum."""
        check = CheckNetworkSpeed(self.valid_params)
        log_parser = check.parse_pod_logs_from_speed_test_func()
        logs = "Ping: 10.5 ms\nDownload: 90.50 Mbit/s\nUpload: 80.20 Mbit/s"
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_upload_fail(self):
        """Tests the log parsing function when upload speed is below minimum."""
        check = CheckNetworkSpeed(self.valid_params)
        log_parser = check.parse_pod_logs_from_speed_test_func()
        logs = "Ping: 10.5 ms\nDownload: 150.75 Mbit/s\nUpload: 40.10 Mbit/s"
        self.assertFalse(log_parser(logs, "node-1"))

    def test_parse_pod_logs_parse_error(self):
        """Tests the log parsing function with malformed log data."""
        check = CheckNetworkSpeed(self.valid_params)
        log_parser = check.parse_pod_logs_from_speed_test_func()
        logs = "Some unexpected output without speed information."
        self.assertFalse(log_parser(logs, "node-1"))

    def test_is_healthy_success(self):
        """Tests is_healthy when the distributed run is successful."""
        self.mock_runner_instance.run_on_all_nodes.return_value = True
        check = CheckNetworkSpeed(self.valid_params)
        self.assertTrue(check.is_healthy())
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()

    def test_is_healthy_failure(self):
        """Tests is_healthy when the distributed run fails."""
        self.mock_runner_instance.run_on_all_nodes.return_value = False
        check = CheckNetworkSpeed(self.valid_params)
        self.assertFalse(check.is_healthy())
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()

    def test_is_healthy_constructs_runner_with_default_image_command(self):
        """Tests that the correct pod template is created for the default image."""
        check = CheckNetworkSpeed(self.valid_params)
        check.is_healthy()

        self.MockDistributedRunner.assert_called_once()
        _, kwargs = self.MockDistributedRunner.call_args

        pod_template = kwargs["pod_template"]
        container = pod_template.spec.containers[0]
        self.assertEqual(container.image, "python:3-alpine")
        self.assertEqual(container.command, ["sh", "-c"])
        self.assertEqual(
            container.args,
            ["apk update && pip3 install speedtest-cli && speedtest-cli --secure"],
        )

    def test_is_healthy_constructs_runner_with_custom_image(self):
        """Tests that the correct pod template is created for a custom image."""
        params = self.valid_params.copy()
        params["image"] = "my-custom/speedtest:latest"
        check = CheckNetworkSpeed(params)
        check.is_healthy()

        _, kwargs = self.MockDistributedRunner.call_args
        container = kwargs["pod_template"].spec.containers[0]
        self.assertEqual(container.image, "my-custom/speedtest:latest")
        self.assertIsNone(container.command)
        self.assertIsNone(container.args)

    def test_run_frequency_logic(self):
        """Tests that the check respects the intervalSeconds."""
        params = self.valid_params.copy()
        params["intervalSeconds"] = 3600  # 1 hour
        check = CheckNetworkSpeed(params)

        # First run
        self.mock_time.return_value = 10000.0
        self.mock_runner_instance.run_on_all_nodes.return_value = True
        self.assertTrue(check.is_healthy())
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()
        self.assertEqual(check.last_run_timestamp, 10000.0)
        self.assertTrue(check.last_run_result)

        # Second run, within interval, should skip and return previous result
        self.mock_time.return_value = 11000.0  # 1000s later
        self.assertTrue(check.is_healthy())
        # run_on_all_nodes should NOT be called again
        self.mock_runner_instance.run_on_all_nodes.assert_called_once()

        # Third run, after interval, should run again
        self.mock_time.return_value = 10000.0 + 3601.0  # 1 hour and 1 sec later
        self.mock_runner_instance.run_on_all_nodes.return_value = False
        self.assertFalse(check.is_healthy())
        self.assertEqual(self.mock_runner_instance.run_on_all_nodes.call_count, 2)
        self.assertEqual(check.last_run_timestamp, 10000.0 + 3601.0)
        self.assertFalse(check.last_run_result)

        # Fourth run, within interval, should skip and return new previous (failed) result
        self.mock_time.return_value = 10000.0 + 3602.0
        self.assertFalse(check.is_healthy())
        self.assertEqual(self.mock_runner_instance.run_on_all_nodes.call_count, 2)