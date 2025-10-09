import unittest
from unittest.mock import MagicMock, patch
import sys

from prometheus_client import REGISTRY
import app

class TestApp(unittest.TestCase):

    def setUp(self):
        self.load_config_patcher = patch('kubernetes.config.load_config')
        self.mock_load_config = self.load_config_patcher.start()
        
        self.apiextensions_v1_api_patcher = patch('kubernetes.client.ApiextensionsV1Api')
        self.mock_apiextensions_v1_api = self.apiextensions_v1_api_patcher.start()

        self.custom_objects_api_patcher = patch('kubernetes.client.CustomObjectsApi')
        self.mock_custom_objects_api = self.custom_objects_api_patcher.start()

        # import app after patch
        self.app = app

        self.create_health_check_cr_patcher = patch('app.create_health_check_cr')
        self.mock_create_health_check_cr = self.create_health_check_cr_patcher.start()

    def tearDown(self):
        self.load_config_patcher.stop()
        self.apiextensions_v1_api_patcher.stop()
        self.custom_objects_api_patcher.stop()
        self.create_health_check_cr_patcher.stop()
        # Unregister metrics to prevent duplicate metric error
        for metric in ['platform_health', 'workload_health']:
            if metric in REGISTRY._names_to_collectors:
                REGISTRY.unregister(REGISTRY._names_to_collectors[metric])

    @patch('app.read_config')
    @patch('app.health_check_cr')
    @patch('app.health_check_map')
    def test_run_checks_onfailure_ignore(self, mock_health_check_map, mock_health_check_cr, mock_read_config):
        # Mock config
        from config import Config
        mock_config = Config(
            platform_checks=[
                {
                    "name": "CheckNodes",
                    "module": "CheckNodes",
                    "onFailure": "ignore"
                },
                {
                    "name": "CheckRobinCluster",
                    "module": "CheckRobinCluster",
                    "onFailure": "fail"
                }
            ],
            workload_checks=[]
        )
        mock_read_config.return_value = mock_config

        # Mock health check modules
        mock_check_nodes_class = MagicMock()
        mock_check_nodes_instance = mock_check_nodes_class.return_value
        mock_check_nodes_instance.is_healthy.return_value = False  # Fails

        mock_check_robin_cluster_class = MagicMock()
        mock_check_robin_cluster_instance = mock_check_robin_cluster_class.return_value
        mock_check_robin_cluster_instance.is_healthy.return_value = False # Fails

        mock_health_check_map.__getitem__.side_effect = lambda key: {
            "CheckNodes": mock_check_nodes_class,
            "CheckRobinCluster": mock_check_robin_cluster_class
        }[key]

        # Run the checks
        self.app.run_checks()

        # Assertions
        mock_health_check_cr.update_status.assert_called_once_with(
            ["CheckRobinCluster"], []
        )

    @patch('app.read_config')
    @patch('app.health_check_cr')
    @patch('app.health_check_map')
    def test_run_checks_onfailure_fail(self, mock_health_check_map, mock_health_check_cr, mock_read_config):
        # Mock config
        from config import Config
        mock_config = Config(
            platform_checks=[
                {
                    "name": "CheckNodes",
                    "module": "CheckNodes",
                    "onFailure": "fail"
                }
            ],
            workload_checks=[]
        )
        mock_read_config.return_value = mock_config

        # Mock health check modules
        mock_check_nodes_class = MagicMock()
        mock_check_nodes_instance = mock_check_nodes_class.return_value
        mock_check_nodes_instance.is_healthy.return_value = False  # Fails

        mock_health_check_map.__getitem__.side_effect = lambda key: {
            "CheckNodes": mock_check_nodes_class
        }[key]

        # Run the checks
        self.app.run_checks()

        # Assertions
        mock_health_check_cr.update_status.assert_called_once_with(
            ["CheckNodes"], []
        )

    @patch('app.read_config')
    @patch('app.health_check_cr')
    @patch('app.health_check_map')
    def test_run_checks_onfailure_default(self, mock_health_check_map, mock_health_check_cr, mock_read_config):
        # Mock config
        from config import Config
        mock_config = Config(
            platform_checks=[
                {
                    "name": "CheckNodes",
                    "module": "CheckNodes"
                }
            ],
            workload_checks=[]
        )
        mock_read_config.return_value = mock_config

        # Mock health check modules
        mock_check_nodes_class = MagicMock()
        mock_check_nodes_instance = mock_check_nodes_class.return_value
        mock_check_nodes_instance.is_healthy.return_value = False  # Fails

        mock_health_check_map.__getitem__.side_effect = lambda key: {
            "CheckNodes": mock_check_nodes_class
        }[key]

        # Run the checks
        self.app.run_checks()

        # Assertions
        mock_health_check_cr.update_status.assert_called_once_with(
            ["CheckNodes"], []
        )

if __name__ == "__main__":
    unittest.main()
