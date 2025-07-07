# Cluster Health Validator

The cluster health validator is a service that runs in-cluster and reports an
aggregated signal of platform and workload health. The health is reported both
as a status as a Kubernetes and as a prometheus metric. This can be used during
cluster provisioning to signal to completion of the pre-staging process or as a
continual sanity check of the state of a cluster.

Alternatively, the cluster health validator can run locally, useful for local
troubleshooting or to use during the cluster provisioning process without
requiring an in-cluster component. 

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
| CheckVirtualMachines | Checks that the expected # of VMs are in a Running State               | **namespace**: namespace to run check against <br >   **count**: (Optional) expected # of VMs |
| CheckDataVolumes     | Checks that the expected # of Data Volumes are 100% imported and ready | **namespace**: namespace to run check against <br >  **count**: (Optional) expected # of DVs |


## Building the image

``` sh
IMAGE_TAG=gcr.io/${PROJECT_ID}/cluster-health-validator:1.0.0
docker build -t ${IMAGE_TAG} .
docker push ${IMAGE_TAG}
```

## Local Usage

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt

python3 app --help
usage: app [-h] [--health-check HEALTH_CHECK [HEALTH_CHECK ...]] [-v | -q] [-w] [-i INTERVAL] [-t TIMEOUT]

options:
  -h, --help            show this help message and exit
  --health-check HEALTH_CHECK [HEALTH_CHECK ...]
                        Set a health check to perform. For health checks requiring parameters, pass them in a key=value format as additional arguments. Example: --health-check
                        checkvirtualmachines namespace=vm-workloads count=3
  -v, --verbose         increase output verbosity; -vv for max verbosity
  -q, --quiet           output errors only
  -w, --wait            wait for health checks to pass before exiting
  -i INTERVAL, --interval INTERVAL
                        interval to poll passing health checks
  -t TIMEOUT, --timeout TIMEOUT
                        Overall timeout for health checks to pass
```

Examples:

```
# Run the default health checks (CheckNodes, CheckRootSyncs, CheckRobinCluster)
python3 app

# Run customized health checks
python3 app --health-check checknodes \
            --health-check checkrobincluster \
            --health-check checkrootsyncs \
            --health-check checkgooglegrouprbac \
            --health-check checkvirtualmachines namespace=vm-workloads count=3 \
            --health-check checkdatavolumes namespace=vm-workloads count=3

# Run default health checks and wait until all health checks pass.
#   Timeout after 1 hour if health checks don't pass
python3 app --wait --interval 60 --timeout 3600

```