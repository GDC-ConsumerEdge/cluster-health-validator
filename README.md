# Cluster Health Validator

The cluster health validator is a service that runs in-cluster and reports an
aggregated signal of platform and workload health. The health is reported both
as a status as a Kubernetes and asa prometheus metric. This can be used during
cluster provisioning to signal to completion of the pre-staging process or as a
continual sanity check of the state of a cluster.



## Building the image

``` sh
IMAGE_TAG=gcr.io/${PROJECT_ID}/cluster-health-validator:1.0.0
docker build -t ${IMAGE_TAG} .
docker push ${IMAGE_TAG}
```

## Pre-requisites

1. Install CRD

```sh
kubectl apply -f app/healthchecks.crd.yaml
```

2. Setup RoleBinding

```sh
kubectl apply -f deploy/cluster-role-binding.yaml
```

## Deploy
```sh
kubectl apply -f deploy/deployment-validator.yaml
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
| CheckRobinCluster    | Checks RobinCluster Health                                             |                                                                      |
| CheckRootSyncs       | Checks that RootSyncs are synced and have completed reconciling        |                                                                      |
| CheckVMRuntime       | Checks that VMruntime is Ready, without any preflight failure          |                                                                      |
| CheckVirtualMachines | Checks that the expected # of VMs are in a Running State               | **namespace**: namespace to run check against   **count**: expected # of VMs |
| CheckDataVolumes     | Checks that the expected # of Data Volumes are 100% imported and ready | **namespace**: namespace to run check against   **count**: expected # of DVs |