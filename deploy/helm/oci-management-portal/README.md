# OCI Management Portal Helm Chart

This chart deploys the Flask/Gunicorn OCI Management Portal container on Kubernetes.

## Build and Push the Image

```bash
docker build -t iad.ocir.io/<ocir-namespace>/oci-management-portal:0.1.0 .
docker push iad.ocir.io/<ocir-namespace>/oci-management-portal:0.1.0
```

If your OCIR repository is private, create an image pull secret and reference it in `imagePullSecrets`.

## Configure Values

Start from the example file:

```bash
cp deploy/helm/oci-management-portal/values.example.yaml my-values.yaml
```

Update:

- `image.repository` and `image.tag`
- `config.appUri` with the public URL used by OIDC callbacks
- `config.tagNamespace`, `config.tagKey`, `config.filterKey`, and `config.cleanupCompartment`
- `config.idmEndpoint` and `config.clientId`
- `secret.clientSecret`

The chart defaults to `config.authType=instance_principal`, which uses the OKE worker node instance principal. Create an OCI dynamic group for the worker node instance or node compartment, then grant that dynamic group the required policies. If you use workload principal instead, set `config.authType=workload_principal` and set `serviceAccount.automount=true`. If you use profile auth, set `config.authType=profile`, set `config.configFile`, and mount your OCI config/key with `extraVolumes` and `extraVolumeMounts`.

For more than one replica, set `config.sessionBackend` to `redis` or `valkey` and provide `config.sessionRedisUrl`. Filesystem sessions are only suitable for a single pod.

## Install

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace oci-management-portal \
  --create-namespace \
  -f my-values.yaml
```

Check rollout:

```bash
kubectl get pods -n oci-management-portal
kubectl logs -n oci-management-portal deploy/oci-management-portal
```

Run the Helm test:

```bash
helm test oci-management-portal -n oci-management-portal
```
