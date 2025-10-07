import unittest
from unittest.mock import MagicMock, patch

from check_data_volumes import CheckDataVolumes
from pydantic import ValidationError


class TestCheckDataVolumes(unittest.TestCase):
    def setUp(self):
        # Mock the Kubernetes client
        self.k8s_client_patcher = patch("check_data_volumes.client")
        self.mock_k8s_client = self.k8s_client_patcher.start()
        self.mock_custom_objects_api = MagicMock()
        self.mock_k8s_client.CustomObjectsApi.return_value = (
            self.mock_custom_objects_api
        )

        # Patch the Prometheus counters
        self.success_counter_patcher = patch("check_data_volumes.DATA_VOLUME_SUCCESS_TOTAL")
        self.mock_success_counter = self.success_counter_patcher.start()
        self.failure_counter_patcher = patch("check_data_volumes.DATA_VOLUME_FAILURE_TOTAL")
        self.mock_failure_counter = self.failure_counter_patcher.start()

    def tearDown(self):
        self.k8s_client_patcher.stop()
        self.success_counter_patcher.stop()
        self.failure_counter_patcher.stop()

    def test_is_healthy_success(self):
        """Test is_healthy returns True and increments success counter when all data volumes are succeeded and count matches."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckDataVolumes(parameters=params)

        mock_dv_list = {
            "items": [
                {
                    "metadata": {"name": "dv1"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "dv2"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_dv_list
        )

        self.assertTrue(checker.is_healthy())
        self.mock_custom_objects_api.list_namespaced_custom_object.assert_called_once_with(
            group="cdi.kubevirt.io",
            version="v1beta1",
            plural="datavolumes",
            namespace="test-ns",
        )
        self.mock_success_counter.labels.assert_called_once_with(namespace="test-ns")
        self.mock_success_counter.labels.return_value.inc.assert_called_once()
        self.mock_failure_counter.labels.assert_not_called()

    def test_is_healthy_incorrect_count(self):
        """Test is_healthy returns False and increments failure counter when the number of data volumes does not match the expected count."""
        params = {"namespace": "test-ns", "count": 3}
        checker = CheckDataVolumes(parameters=params)

        mock_dv_list = {
            "items": [
                {
                    "metadata": {"name": "dv1"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "dv2"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_dv_list
        )

        self.assertFalse(checker.is_healthy())
        self.mock_failure_counter.labels.assert_called_once_with(namespace="test-ns")
        self.mock_failure_counter.labels.return_value.inc.assert_called_once()
        self.mock_success_counter.labels.assert_not_called()

    def test_is_healthy_phase_not_succeeded(self):
        """Test is_healthy returns False and increments failure counter when a data volume phase is not 'Succeeded'."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckDataVolumes(parameters=params)

        mock_dv_list = {
            "items": [
                {
                    "metadata": {"name": "dv1"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {"metadata": {"name": "dv2"}, "status": {"phase": "Pending"}},
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_dv_list
        )

        self.assertFalse(checker.is_healthy())
        self.mock_failure_counter.labels.assert_called_once_with(namespace="test-ns")
        self.mock_failure_counter.labels.return_value.inc.assert_called_once()
        self.mock_success_counter.labels.assert_not_called()

    def test_is_healthy_progress_not_complete(self):
        """Test is_healthy returns False and increments failure counter when a data volume progress is not '100.0%'."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckDataVolumes(parameters=params)

        mock_dv_list = {
            "items": [
                {
                    "metadata": {"name": "dv1"},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "dv2"},
                    "status": {"phase": "Succeeded", "progress": "50.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_dv_list
        )

        self.assertFalse(checker.is_healthy())
        self.mock_failure_counter.labels.assert_called_once_with(namespace="test-ns")
        self.mock_failure_counter.labels.return_value.inc.assert_called_once()
        self.mock_success_counter.labels.assert_not_called()

    def test_is_healthy_no_datavolumes_expected(self):
        """Test is_healthy returns True and increments success counter when no data volumes are found and count is 0."""
        params = {"namespace": "test-ns", "count": 0}
        checker = CheckDataVolumes(parameters=params)

        mock_dv_list = {"items": []}
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_dv_list
        )

        self.assertTrue(checker.is_healthy())
        self.mock_success_counter.labels.assert_called_once_with(namespace="test-ns")
        self.mock_success_counter.labels.return_value.inc.assert_called_once()
        self.mock_failure_counter.labels.assert_not_called()

    def test_init_invalid_parameters(self):
        """Test that initializing with invalid parameters raises a ValidationError."""
        # Missing 'namespace'
        with self.assertRaises(ValidationError):
            CheckDataVolumes(parameters={"count": 1})

        # Invalid type for 'count'
        with self.assertRaises(ValidationError):
            CheckDataVolumes(parameters={"namespace": "test-ns", "count": "two"})

    def test_init_optional_parameters(self):
        """Test initilializing with optional parameters."""
        # Optional 'count'
        check = CheckDataVolumes(parameters={"namespace": "test-ns"})
        self.assertIsNone(check.count)
 