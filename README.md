## Pre-requisites

1. Install CRD

```sh
kubectl apply -f app/healthchecks.crd.yaml
```

2. Setup RoleBinding

TODO: Restrict to the required roles resources to check the health status of k8s resources.

```sh
kubectl apply -f deploy/cluster-role-binding.yaml
```

## Deploy
```sh
kubectl apply -f deploy/deployment-validator.yaml
```


## Building image

``` sh
IMAGE_TAG=gcr.io/cloud-alchemists-sandbox/kamek/cluster-health-validator:0.0.6
docker run -t ${IMAGE_TAG} .
docker push ${IMAGE_TAG}
```

