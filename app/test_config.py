import unittest
import os
import yaml
from pydantic import ValidationError
from config import read_config

class TestConfig(unittest.TestCase):
    def test_complete_config(self):
        os.environ['APP_CONFIG_PATH'] = 'testdata/complete_config.yaml'
        result = read_config()
        self.assertEqual(len(result.platform_checks), 4)
        self.assertEqual(len(result.workload_checks), 2)

    def test_complete_config(self):
        os.environ['APP_CONFIG_PATH'] = 'testdata/platform_only_config.yaml'
        result = read_config()
        self.assertEqual(len(result.platform_checks), 4)
        self.assertEqual(len(result.workload_checks), 0)

    def test_invalid_yaml(self):
        os.environ['APP_CONFIG_PATH'] = 'testdata/invalid_config.yaml'
        self.assertRaises(yaml.YAMLError, read_config)

    def test_required_fields(self):
        os.environ['APP_CONFIG_PATH'] = 'testdata/missing_required.yaml'
        self.assertRaises(ValidationError, read_config)