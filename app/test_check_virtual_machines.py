import unittest
from unittest.mock import MagicMock, patch

from check_virtual_machines import CheckVirtualMachines
from pydantic import ValidationError


class TestCheckVirtualMachines(unittest.TestCase):
    def setUp(self):
        # Mock the Kubernetes client
        self.k8s_client_patcher = patch("check_virtual_machines.client")
        self.mock_k8s_client = self.k8s_client_patcher.start()
        self.mock_custom_objects_api = MagicMock()
        self.mock_k8s_client.CustomObjectsApi.return_value = (
            self.mock_custom_objects_api
        )

    def tearDown(self):
        self.k8s_client_patcher.stop()

    def test_is_healthy_success(self):
        """Test is_healthy returns True when all VMs are running and count matches."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckVirtualMachines(parameters=params)

        mock_vm_list = {
            "items": [
                {
                    "metadata": {"name": "vm1"},
                    "status": {"state": "Running"},
                },
                {
                    "metadata": {"name": "vm2"},
                    "status": {"state": "Running"},
                },
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_vm_list
        )

        self.assertTrue(checker.is_healthy())
        

        self.mock_custom_objects_api.list_namespaced_custom_object.assert_called_once_with(
            group="vm.cluster.gke.io",
            version="v1",
            plural="virtualmachines",
            namespace="test-ns",
        )

    def test_is_healthy_incorrect_count(self):
        """Test is_healthy returns False when the number of VMs does not match the expected count."""
        params = {"namespace": "test-ns", "count": 3}
        checker = CheckVirtualMachines(parameters=params)

        mock_vm_list = {
            "items": [
                {"metadata": {"name": "vm1"}, "status": {"state": "Running"}},
                {"metadata": {"name": "vm2"}, "status": {"state": "Running"}},
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_vm_list
        )

        self.assertFalse(checker.is_healthy())

    def test_is_healthy_vm_not_running(self):
        """Test is_healthy returns True when a VM is not in the 'Running' state."""
        params = {"namespace": "test-ns", "count": 2}
        checker = CheckVirtualMachines(parameters=params)

        mock_vm_list = {
            "items": [
                {"metadata": {"name": "vm1"}, "status": {"state": "Running"}},
                {"metadata": {"name": "vm2"}, "status": {"state": "Stopped"}},
            ]
        }
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_vm_list
        )

        self.assertTrue(checker.is_healthy())

    def test_init_invalid_parameters(self):
        """Test that initializing with invalid parameters raises a ValidationError."""
        # Missing 'namespace'
        with self.assertRaises(ValidationError):
            CheckVirtualMachines(parameters={"count": "1"})

        # Invalid type for 'count'
        with self.assertRaises(ValidationError):
            CheckVirtualMachines(parameters={"namespace": "test-ns", "count": "two"})

    def test_init_optional_parameters(self):
        """Test initilializing with optional parameters."""
        # Optional 'count'
        check = CheckVirtualMachines(parameters={"namespace": "test-ns"})
        self.assertIsNone(check.count)

    def test_is_healthy_no_vms_expected(self):
        """Test is_healthy returns True when no VMs are found and count is 0."""
        params = {"namespace": "test-ns", "count": 0}
        checker = CheckVirtualMachines(parameters=params)

        mock_vm_list = {"items": []}
        self.mock_custom_objects_api.list_namespaced_custom_object.return_value = (
            mock_vm_list
        )

        self.assertTrue(checker.is_healthy())