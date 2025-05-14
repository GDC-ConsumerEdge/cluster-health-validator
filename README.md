# Cluster Health Validator

The cluster health validator is a service that runs in-cluster and reports an
aggregated signal of platform and workload health. The health is reported both
as a status as a Kubernetes and asa prometheus metric. This can be used during
cluster provisioning to signal to completion of the pre-staging process or as a
continual sanity check of the state of a cluster.

## Installation

This project uses a CRD and operator, and requires Cluster-Level access. The project can be deployed as a `RootSync` config-sync object with the following configuration. NOTE: Production use should clone the repo, make it private and use the `token` appraoch to authentiate to private repo.

```yaml
# root-sync.yaml
apiVersion: configsync.gke.io/v1beta1
kind: RootSync
metadata:
  name: "cluster-health-validator"
  namespace: config-management-system
  annotations:
    configsync.gke.io/deletion-propagation-policy: Foreground # indicate that cascade delete is preferred
spec:
  sourceFormat: "unstructured"
  git:
    repo: "https://github.com/GDC-ConsumerEdge/cluster-health-validator.git"
    branch: "main"
    period: "24h"                                       # check for changes every day
    dir: "/config/default"
    auth: "none"                                        # Production use, use "token" after forking repo
    #auth: "token"
    #secretRef:
    #  name: "git-creds"
```

## Configuration

Cluster Health Validator allows customization for which platform and workload health checks are performed. This is specified as part of the ConfigMap as part of the deployment.

```
apiVersion: v1
kind: ConfigMap
metadata:
  name: health-check-config
data:
  config.yaml: |
    platform_checks:
    - name: Node Health
      module: CheckNodes
    - name: Robin Cluster Health
      module: CheckRobinCluster
    - name: Root Sync Check
      module: CheckRootSyncs
    - name: VMRuntime Check
      module: CheckVMRuntime

    workload_checks:
    - name: VM Workloads Health
      module: CheckVirtualMachines
      parameters:
        namespace: vm-workloads
        count: 4
    - name: VM Data Volume Health
      module: CheckDataVolumes
      parameters:
        namespace: vm-workloads
        count: 4
```

Below details the health check modules available as part of the solution, with some requiring parameters:

| Module               | Description                                                            | Parameters                                                           |
|----------------------|------------------------------------------------------------------------|----------------------------------------------------------------------|
| CheckNodes           | Checks Kubernetes Node Health                                          |                                                                      |
| CheckGoogleGroupRBAC | Checks that Google Group RBAC has been enabled                         |                                                                      |
| CheckRobinCluster    | Checks RobinCluster Health                                             |                                                                      |
| CheckRootSyncs       | Checks that RootSyncs are synced and have completed reconciling        |                                                                      |
| CheckVMRuntime       | Checks that VMruntime is Ready, without any preflight failure          |                                                                      |
| CheckVirtualMachines | Checks that the expected # of VMs are in a Running State               | **namespace**: namespace to run check against   **count**: expected # of VMs |
| CheckDataVolumes     | Checks that the expected # of Data Volumes are 100% imported and ready | **namespace**: namespace to run check against   **count**: expected # of DVs |


## Building the image

``` sh
IMAGE_TAG=gcr.io/${PROJECT_ID}/cluster-health-validator:1.0.0
docker build -t ${IMAGE_TAG} .
docker push ${IMAGE_TAG}
```
