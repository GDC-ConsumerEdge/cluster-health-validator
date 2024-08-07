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



