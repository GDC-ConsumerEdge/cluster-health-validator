import unittest
from unittest.mock import MagicMock, patch

from check_virtual_machine_disks import CheckVirtualMachineDisks
from pydantic import ValidationError


class TestCheckVirtualMachineDisks(unittest.TestCase):
    def setUp(self):
        # Mock the Kubernetes client
        self.k8s_client_patcher = patch("check_virtual_machine_disks.client")
        self.mock_k8s_client = self.k8s_client_patcher.start()
        self.mock_custom_objects_api = MagicMock()
        self.mock_k8s_client.CustomObjectsApi.return_value = (
            self.mock_custom_objects_api
        )

    def tearDown(self):
        self.k8s_client_patcher.stop()

    def test_is_healthy_success(self):
        """Test is_healthy returns True when all disks are Succeeded and count matches."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {
            "items": [
                {
                    "metadata": {"name": "disk1", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "disk2", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertTrue(checker.is_healthy())
        self.mock_custom_objects_api.list_namespaced_custom_object.assert_called_once_with(
            group="vm.cluster.gke.io",
            version="v1",
            plural="virtualmachinedisks",
            namespace="test-ns",
        )

    def test_is_healthy_restored_disk_label(self):
        """Test is_healthy returns True for a restored disk even if not fully imported."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {
            "items": [
                {
                    "metadata": {"name": "disk1", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {
                        "name": "disk2",
                        "labels": {"vm.cluster.gke.io/virtual-machine-restore": "true"},
                    },
                    "status": {"phase": "Succeeded"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertTrue(checker.is_healthy())
        
    def test_is_not_suceeded(self):
        """Test is_healthy returns False when the number of disks does not match the expected count."""
        params = {"namespace": "test-ns", "count": 1}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {
            "items": [
                {
                    "metadata": {"name": "disk1_inprogress", "labels": {}},
                    "status": {"phase": "Inprogress", "progress": "100.0%"},
                }
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertFalse(checker.is_healthy())
        
    def test_is_healthy_incorrect_count(self):
        """Test is_healthy returns False when the number of disks does not match the expected count."""
        params = {"namespace": "test-ns", "count": 3}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {
            "items": [
                {
                    "metadata": {"name": "disk1", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "disk2", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertFalse(checker.is_healthy())


    def test_is_healthy_disk_not_imported(self):
        """Test is_healthy returns False when a disk has not been fully imported."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {
            "items": [
                {
                    "metadata": {"name": "disk1", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "100.0%"},
                },
                {
                    "metadata": {"name": "disk2_50percent", "labels": {}},
                    "status": {"phase": "Succeeded", "progress": "50.0%"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertFalse(checker.is_healthy())


    def test_init_invalid_parameters(self):
        """Test that initializing with invalid parameters raises a ValidationError."""
        # Missing 'namespace'
        with self.assertRaises(ValidationError):
            CheckVirtualMachineDisks(parameters={"count": "1"})

        # Invalid type for 'count'
        with self.assertRaises(ValidationError):
            CheckVirtualMachineDisks(
                parameters={"namespace": "test-ns", "count": "two"}
            )

    def test_init_optional_parameters(self):
        """Test initilializing with optional parameters."""
        # Optional 'count'
        check = CheckVirtualMachineDisks(parameters={"namespace": "test-ns"})
        self.assertIsNone(check.count)

    def test_is_healthy_no_disks_expected(self):
        """Test is_healthy returns True when no disks are found and count is 0."""
        params = {"namespace": "test-ns", "count": 0}
        checker = CheckVirtualMachineDisks(parameters=params)

        mock_disk_list = {"items": []}
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_disk_list
        )

        self.assertTrue(checker.is_healthy())


if __name__ == "__main__":
    unittest.main()