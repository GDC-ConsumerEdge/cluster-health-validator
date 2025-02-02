import os
from typing import NotRequired

import yaml
from pydantic import BaseModel
from typing_extensions import TypedDict

"""
Example health check configuration

platform_checks:
- name: Node Health
  module: CheckNodes
- name: Robin Cluster Health
  module: CheckRobinCluster

workload_checks:
- name: VM Workloads Health
  module: CheckVirtualMachines
  parameters:
    namespace: vm-workloads
"""


class HealthCheck(TypedDict):
    name: str
    module: str
    parameters: NotRequired[dict] = {}


class Config(BaseModel):
    platform_checks: list[HealthCheck]
    workload_checks: list[HealthCheck]


def read_config():
    with open(os.environ.get("APP_CONFIG_PATH", "/config/config.yaml")) as stream:
        config = yaml.safe_load(stream)
    return Config(**config)
