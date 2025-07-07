import os
import unittest
from unittest.mock import mock_open, patch

import yaml
from config import read_config
from pydantic import ValidationError


class TestConfig(unittest.TestCase):
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
platform_checks:
  - { name: p1, module: m1 }
  - { name: p2, module: m2 }
  - { name: p3, module: m3 }
  - { name: p4, module: m4 }
workload_checks:
  - { name: w1, module: m5 }
  - { name: w2, module: m6 }
network_checks:
  - { name: n1, module: m7 }
""",
    )
    def test_complete_config(self, mock_file):
        result = read_config()
        self.assertEqual(len(result.platform_checks), 4)
        self.assertEqual(len(result.workload_checks), 2)
        self.assertEqual(len(result.network_checks), 1)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
platform_checks:
  - { name: p1, module: m1 }
  - { name: p2, module: m2 }
  - { name: p3, module: m3 }
  - { name: p4, module: m4 }
workload_checks: []
""",
    )
    def test_backward_compatible_config(self, mock_file):
        result = read_config()
        self.assertEqual(len(result.platform_checks), 4)
        self.assertEqual(len(result.workload_checks), 0)
        self.assertEqual(len(result.network_checks), 0)

    @patch("builtins.open", new_callable=mock_open, read_data="platform_checks: -")
    def test_invalid_yaml(self, mock_file):
        self.assertRaises(yaml.YAMLError, read_config)

    @patch(
        "builtins.open", new_callable=mock_open, read_data="some_other_property: 123"
    )
    def test_all_fields_optional(self, mock_file):
        result = read_config()
        self.assertEqual(len(result.platform_checks), 0)
        self.assertEqual(len(result.workload_checks), 0)
        self.assertEqual(len(result.network_checks), 0)
