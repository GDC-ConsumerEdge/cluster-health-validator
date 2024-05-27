## Pre-requisites


1. Install CRD

```
kubectl apply -f app/healthchecks.crd.yaml
```


2. Setup RoleBinding

TODO: Restrict to the required roles resources to check the health status of k8s resources.

```
kubectl apply -f deploy/cluster-role-binding.yaml
```
