# OCI Management Portal Deployment Guide

[![Deploy to Oracle Cloud](https://oci-resourcemanager-plugin.plugins.oci.oraclecloud.com/latest/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https://github.com/flynnkc/oci-management-portal/archive/refs/tags/v0.99.9.zip)

This guide is a deployment runbook for the OCI Management Portal. It contains only the prerequisites, configuration inputs, deployment steps, and validation checks required to run the application.

Use this guide for two deployment paths:

- **Production path**: provision OCI infrastructure with Terraform through OCI Resource Manager, then deploy the application to OKE with Helm.
- **Local testing path**: use [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md) to run the portal from a workstation or single host and configure the confidential application for login.

This document is intentionally ordered with the automated Terraform and Helm deployment first, followed by the local/manual path.

For architecture, component explanations, authentication flow details, and lifecycle context, see [README.md](README.md). For the manual and workstation path, use [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md).

## Table of Contents

1. [Deployment Paths](#deployment-paths)
2. [Common Prerequisites](#common-prerequisites)
3. [Required Configuration Inputs](#required-configuration-inputs)
4. [Production Deployment Overview](#production-deployment-overview)
5. [Production Step 1: Deploy Infrastructure with OCI Resource Manager](#production-step-1-deploy-infrastructure-with-oci-resource-manager)
6. [Production Step 2: Prepare OKE Access](#production-step-2-prepare-oke-access)
7. [Production Step 3: Build and Push the Image to OCIR](#production-step-3-build-and-push-the-image-to-ocir)
8. [Production Step 4: Configure Runtime IAM](#production-step-4-configure-runtime-iam)
9. [Production Step 5: Deploy with Helm](#production-step-5-deploy-with-helm)
10. [Production Step 6: Update Identity Redirects if Needed](#production-step-6-update-identity-redirects-if-needed)
11. [Post-Deployment Validation](#post-deployment-validation)
12. [Deployment Troubleshooting](#deployment-troubleshooting)
13. [Useful References](#useful-references)

## Deployment Paths

| Path | Purpose | Output |
|---|---|---|
| Production deployment | Provision infrastructure and run the portal on OKE | OKE-hosted application exposed through LoadBalancer or ingress |
| Local testing deployment | Validate app configuration, confidential app setup, OIDC login, OCI auth, search, extend, delete, and export behavior outside the automated OKE path | Flask or Gunicorn process on port `5000` |

Recommended order for a new environment:

1. Complete common prerequisites.
2. Provision OCI infrastructure with Terraform through OCI Resource Manager.
3. Build and push the image to OCIR.
4. Deploy the Helm chart to OKE.
5. Validate login, search, extend, delete, readiness, and logs.
6. Use the local testing path when you need workstation-based validation, troubleshooting, or a manual single-host run.

## Common Prerequisites

Before using either deployment path, confirm the following.

### OCI tenancy prerequisites

- OCI tenancy access with permission to create or use:
  - compartments,
  - OCI Identity Domain applications,
  - OKE resources for production deployment,
  - OCIR repositories for production deployment,
  - IAM policies and dynamic groups.
- Existing OCI Identity Domain for OIDC login.
- Cleanup compartment OCID for resources marked for deletion.
- Tagging model for managed resources:
  - tag namespace,
  - owner or creator tag key,
  - expiry filter namespace,
  - expiry filter key.

### Identity Domain prerequisites

Create or reuse an OCI Identity Domain confidential application.

Required OIDC values:

- Identity Domain endpoint
- Confidential application client ID
- Confidential application client secret
- Redirect URI matching the deployed application URL plus `/callback`
- Post logout redirect URI matching the application base URL, if used

Examples:

```text
Local:
http://localhost:5000/callback

Single-host manual deployment:
http://<public-ip>:5000/callback

Production with HTTPS:
https://<portal-domain>/callback
```

### Tooling prerequisites

For local testing:

- Python `3.11+`
- Git
- OCI CLI profile or another supported OCI auth mode

For production:

- OCI Console access
- OCI Cloud Shell or a workstation with:
  - `oci` CLI
  - `kubectl`
  - `helm`
  - `docker`
- OCI Resource Manager access
- Kubernetes access to the target OKE cluster after provisioning

## Required Configuration Inputs

The application reads runtime settings through environment variables prefixed with `OCI_MGMT_DASH_`.

### Required app values

| Variable | Sample Values | Description |
|---|---|---|
| `OCI_MGMT_DASH_TAG_NAMESPACE` | `Usage-Management` | Namespace used to identify managed resources |
| `OCI_MGMT_DASH_TAG_KEY` | `Owner` | Owner or creator tag key |
| `OCI_MGMT_DASH_FILTER_NAMESPACE` | `Usage-Management` | Namespace used with `FILTER_KEY` |
| `OCI_MGMT_DASH_FILTER_KEY` | `Expires` | Expiry filter key |
| `OCI_MGMT_DASH_CLEANUP_CMP` | `ocid1.compartment.oc1..abcdefg...` | Cleanup compartment OCID |
| `OCI_MGMT_DASH_IDM_ENDPOINT` | `https://idcs-xxxxxxx.identity.com` | OCI Identity Domain endpoint |
| `OCI_MGMT_DASH_CLIENT_ID` | `<CLIENT_ID>` | OIDC confidential application client ID |
| `OCI_MGMT_DASH_CLIENT_SECRET` | `<CLIENT_SECRET>` | OIDC confidential application client secret |
| `OCI_MGMT_DASH_APP_URI` | `http://localhost:5000` | Public application base URL |
| `OCI_MGMT_DASH_AUTH_TYPE` | `profile` | `profile`, `instance_principal`, `delegation_token`, `workload_principal`, or `resource_principal` |
| `OCI_MGMT_DASH_LOG_LEVEL` | `info` | Application log level |

### Common optional app values

| Variable | Sample Values | Description |
|---|---|---|
| `OCI_MGMT_DASH_PROXY` | `false` | Set `true` when behind trusted reverse proxy or ingress |
| `OCI_MGMT_DASH_CONFIG_FILE` | `~/.oci/config` | OCI config file for profile auth |
| `OCI_MGMT_DASH_PROFILE` | `DEFAULT` | OCI profile name |
| `OCI_MGMT_DASH_SESSION_BACKEND` | `filesystem` | `filesystem`, `redis`, or `valkey` |
| `OCI_MGMT_DASH_SESSION_REDIS_URL` | unset | Required for Redis/Valkey session backend |
| `OCI_MGMT_DASH_USER_SCOPED_OCI_CALLS` | `false` | Uses per-user token exchange signers for Search/Delete/Extend when enabled |

For a complete sample, start from [sample.env](sample.env).

## Production Deployment Overview

The production deployment path has two layers.

| Layer | Tooling | Purpose |
|---|---|---|
| Infrastructure | Terraform through OCI Resource Manager | Creates or configures OKE, networking, IAM baseline, Identity Domain confidential app, and identity propagation trust |
| Application | Helm on OKE | Deploys the OCI Management Portal container and runtime configuration |

Production deployment order:

1. Create OCI Resource Manager stack from `deploy/terraform/`.
2. Apply Terraform and capture outputs.
3. Configure kubeconfig for the OKE cluster.
4. Build and push the application image to OCIR.
5. Configure runtime IAM for the worker node identity or chosen auth mode.
6. Create Kubernetes namespace and secrets.
7. Deploy the Helm chart.
8. Validate rollout and login.
9. Update Identity Domain redirects if the final URL changed.

## Production Step 1: Deploy Infrastructure with OCI Resource Manager

### 1. Prepare Terraform stack source

Create a ZIP archive from the contents of the [deploy/terraform](deploy/terraform/) directory.

Include:

- all `.tf` files,
- `schema.yaml`,
- supporting Terraform files in `deploy/terraform/`.

Do not upload the full repository if the Resource Manager stack only needs the infrastructure layer.

### 2. Create the Resource Manager stack

In OCI Console:

1. Open `Developer Services`.
2. Open `Resource Manager`.
3. Select `Stacks`.
4. Click `Create stack`.
5. Upload the Terraform ZIP from `deploy/terraform/`.
6. Choose the target compartment.
7. Review the variable form rendered from `schema.yaml`.

### 3. Enter required Terraform variables

| Variable | Required input |
|---|---|
| `compartment_ocid` | Compartment for network and OKE resources |
| `identity_domain_id` | Existing OCI Identity Domain OCID |
| `label` | Resource naming prefix |
| `confidential_application_base_url` | Expected public portal URL |
| `worker_ssh_public_key` | SSH public key for worker nodes, if needed |
| `node_shape` | OKE worker node shape |
| `node_ocpus` | Worker node OCPU count |
| `node_memory` | Worker node memory |
| `k8s_version` | Kubernetes version, if pinning |

If the final public application URL is not known yet, use a temporary base URL and update it after Helm creates the final LoadBalancer or ingress URL.

### 4. Review deployment-sensitive networking inputs

Before applying, confirm:

- whether external `kubectl` access should be enabled,
- allowed CIDR for load balancer ingress,
- whether HTTP port `80` should be enabled,
- whether the default VCN and subnet CIDRs are acceptable,
- whether private OKE API endpoint access matches your operating model.

### 5. Run Terraform plan and apply

From the Resource Manager stack:

1. Run `Plan`.
2. Review resources and networking changes.
3. Run `Apply`.
4. Wait for completion.

### 6. Capture Terraform outputs

Record these outputs for Helm:

| Terraform output | Helm value |
|---|---|
| `identity_domain_endpoint` | `config.idmEndpoint` |
| `confidential_application_client_id` | `config.clientId` |
| `confidential_application_client_secret` | `secret.clientSecret` |

Also retain:

- `confidential_application_ocid`,
- `identity_propagation_trust_ocid`.

### 7. Validate infrastructure

Confirm:

- OKE cluster exists,
- node pool exists,
- worker nodes are available or can become available,
- Identity Domain confidential application exists,
- stack outputs are available,
- cleanup compartment OCID is known.

## Production Step 2: Prepare OKE Access

**Note: Run from OCI Cloud Shell or an OCI CLI workstation.**


### Clone the project repository and setup the Kubeconfig

Run this from OCI Cloud Shell or from the workstation you will use for the deployment:

```bash
git clone https://github.com/flynnkc/oci-management-portal.git
cd oci-management-portal
```

Confirm the repository contains the deployment assets. This local clone is required because the Helm chart, Terraform source files, and runtime configuration examples are all taken from the repository. Now proceed with the below steps.


```bash
export REGION="us-ashburn-1"
export CLUSTER_OCID="<cluster-ocid>"
```

Create or update kubeconfig:

```bash
oci ce cluster create-kubeconfig \
  --cluster-id "${CLUSTER_OCID}" \
  --file "$HOME/.kube/config" \
  --region "${REGION}" \
  --token-version 2.0.0 \
  --kube-endpoint PUBLIC_ENDPOINT
```

If the cluster uses a private endpoint:

```bash
oci ce cluster create-kubeconfig \
  --cluster-id "${CLUSTER_OCID}" \
  --file "$HOME/.kube/config" \
  --region "${REGION}" \
  --token-version 2.0.0 \
  --kube-endpoint PRIVATE_ENDPOINT
```

Validate:

```bash
kubectl config current-context
kubectl get nodes
kubectl get pods -A
```

## Production Step 3: Build and Push the Image to OCIR

Run from the repository root where the `Dockerfile` exists.

### 1. Set image variables

```bash
export REGION="us-ashburn-1"
export REGISTRY="ocir.${REGION}.oci.oraclecloud.com"
export OCIR_NAMESPACE="$(oci os ns get --query data --raw-output)"
export REPO_NAME="oci-management-portal"
export IMAGE_TAG="$(date +%Y%m%d%H%M)"
export IMAGE_REPOSITORY="${REGISTRY}/${OCIR_NAMESPACE}/${REPO_NAME}"
export IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
export COMPARTMENT_OCID="<compartment-ocid-for-ocir-repository>"
```

### 2. Create OCIR repository if needed

```bash
oci artifacts container repository create \
  --display-name "${REPO_NAME}" \
  --compartment-id "${COMPARTMENT_OCID}"
```

If the repository already exists, continue.

### 3. Log in to OCIR

Generate an OCI auth token for your user, then run:

```bash
read -r -p "OCIR username: " OCIR_USERNAME
read -r -s -p "OCIR auth token: " OCIR_AUTH_TOKEN
echo

printf '%s' "${OCIR_AUTH_TOKEN}" | docker login "${REGISTRY}" \
  --username "${OCIR_USERNAME}" \
  --password-stdin
```

Common username formats:

```text
If your are executing this via default domain : <tenancy-namespace>/<username>
If your are executing this via non- default domain: <tenancy-namespace>/<identity-domain>/<username>
```

### 4. Build and push

```bash
docker build -t "${REPO_NAME}:local" .
docker tag "${REPO_NAME}:local" "${IMAGE}"
docker push "${IMAGE}"
```

**Note: Use Podman if your system does not support docker**

## Production Step 4: Configure Runtime IAM

The Helm chart defaults to:

```text
config.authType = instance_principal
```

For instance principal auth:

1. Identify the OKE worker node instance OCID or node compartment OCID.
2. Create a dynamic group matching the worker node instance or node compartment. 
  *Example matching rule: All {instance.compartment.id = 'ocid1.compartment.oc1..aaaaaaaavegzwsigdvyjtsq5ryqujwckz5jmxxxxxxxxxxxxxxxxxxxxxx'}*
3. Add IAM policies for portal runtime access.

Initial validation policy examples:

```text
Allow dynamic-group <dynamic-group-name> to inspect compartments in tenancy
Allow dynamic-group <dynamic-group-name> to read usage-reports in tenancy
Allow dynamic-group <dynamic-group-name> to read all-resources in tenancy
```


## Production Step 5: Deploy with Helm

### 1. Create namespace

```bash
export APP_NAMESPACE="oci-management-portal"
kubectl create namespace "${APP_NAMESPACE}"
```

If the namespace already exists, continue.

### 2. Create image pull secret

```bash
kubectl create secret docker-registry ocirsecret \
  --namespace "${APP_NAMESPACE}" \
  --docker-server="${REGISTRY}" \
  --docker-username="${OCIR_USERNAME}" \
  --docker-password="${OCIR_AUTH_TOKEN}" \
  --docker-email="unused@example.com"
```

If the secret already exists, update or recreate it according to your cluster policy.

### 3. Create application secret

Use the Terraform output `confidential_application_client_secret`.

```bash
kubectl create secret generic oci-management-portal-secrets \
  --namespace "${APP_NAMESPACE}" \
  --from-literal=OCI_MGMT_DASH_CLIENT_SECRET="<oidc-client-secret>"
```

### 4. Create values file

Update the exixting file with your vaules :[deploy/helm/oci-management-portal/my-values.yaml](deploy/helm/oci-management-portal/my-values.yaml)

```bash
vi my-values.yaml
```

Set these values:

| Helm value | Source |
|---|---|
| `image.repository` | `${IMAGE_REPOSITORY}` |
| `image.tag` | `${IMAGE_TAG}` |
| `imagePullSecrets[0].name` | `ocirsecret` |
| `config.appUri` | Public portal URL |
| `config.proxy` | `"true"` when behind load balancer or ingress |
| `config.tagNamespace` | Managed tag namespace |
| `config.tagKey` | Owner or creator tag key |
| `config.filterNamespace` | Expiry filter namespace |
| `config.filterKey` | Expiry filter key |
| `config.cleanupCompartment` | Cleanup compartment OCID |
| `config.authType` | Usually `instance_principal` |
| `config.idmEndpoint` | Terraform `identity_domain_endpoint` |
| `config.clientId` | Terraform `confidential_application_client_id` |
| `secret.create` | `false` if using existing Kubernetes secret |
| `secret.existingSecret` | `oci-management-portal-secrets` |
| `service.type` | `LoadBalancer` or `ClusterIP` with ingress |

For more than one replica:

- set `config.sessionBackend` to `redis` or `valkey`,
- provide `config.sessionRedisUrl`,
- provide Redis/Valkey password through secret configuration if required.

Filesystem sessions are suitable only for a single pod.



### 5. Install or upgrade Helm release

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace "${APP_NAMESPACE}" \
  --create-namespace \
  -f my-values.yaml
```

### 6. Check rollout

```bash
kubectl get pods -n "${APP_NAMESPACE}"
kubectl get svc -n "${APP_NAMESPACE}"
kubectl logs -n "${APP_NAMESPACE}" deploy/oci-management-portal
```

Run Helm test:

```bash
helm test oci-management-portal -n "${APP_NAMESPACE}"
```

## Production Step 6: Update Identity Redirects if Needed

After the service or ingress receives its final URL, confirm the URL matches:

- Helm `config.appUri`,
- OCI Identity Domain redirect URI,
- Terraform `confidential_application_base_url` or explicit redirect URI variables.

If the final URL changed after Helm deployment:

1. Update the Resource Manager stack variable `confidential_application_base_url`, or the explicit redirect URI variables if used.
2. Run `Plan`.
3. Run `Apply`.
4. Confirm the Identity Domain application includes:

```text
https://<final-portal-url>/callback
```

5. Update Helm values if `config.appUri` changed.
6. Redeploy Helm if needed:

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace "${APP_NAMESPACE}" \
  -f my-values.yaml
```

## Post-Deployment Validation

### Infrastructure validation

```bash
kubectl get nodes
kubectl get pods -n "${APP_NAMESPACE}"
kubectl get svc -n "${APP_NAMESPACE}"
kubectl get events -n "${APP_NAMESPACE}" --sort-by=.lastTimestamp
```

Confirm:

- OKE cluster is active.
- Worker nodes are `Ready`.
- Portal pod is running.
- Service or ingress exposes the application as expected.
- Dynamic group and IAM policies are in place.

### Application validation

```bash
kubectl logs -n "${APP_NAMESPACE}" deploy/oci-management-portal
```

Check:

- `/health` returns healthy.
- `/ready` returns ready.
- Login redirects to OCI Identity Domain.
- Login callback succeeds.
- Home page loads without server errors.
- Search returns expected expired resources.
- Cost data is visible after cache warm-up.
- CSV export works.
- Extend action updates a supported test resource.
- Delete action moves a supported test resource to the configured cleanup compartment.

### Optional port-forward validation

If the service is not publicly exposed yet:

```bash
kubectl port-forward -n "${APP_NAMESPACE}" deploy/oci-management-portal 5000:5000
```

Then open:

```text
http://localhost:5000
```

## Deployment Troubleshooting

### Login fails after deployment

Check:

- `config.appUri`,
- Identity Domain redirect URI,
- Terraform `confidential_application_base_url`,
- `config.idmEndpoint`,
- `config.clientId`,
- Kubernetes secret value for `OCI_MGMT_DASH_CLIENT_SECRET`,
- Identity Domain sign-on policy.

If the public URL changed after Helm created the LoadBalancer, update Terraform and Helm values.

### Pod is running but users are logged out unexpectedly

Check:

- replica count,
- `config.sessionBackend`,
- Redis/Valkey connection settings,
- ingress or load balancer session affinity if user-scoped OCI calls are enabled.

Use `filesystem` sessions only for a single pod.

### `/ready` fails or cost is empty

Check:

- `read usage-reports` policy,
- runtime auth mode,
- dynamic group membership,
- OCI Usage API errors in logs.

### Search returns no resources

Check:

- tag namespace and key,
- filter namespace and key,
- selected region,
- resource expiry values,
- owner/creator tag value,
- OCI Search permissions.

### Delete or extend action is unavailable

Check:

- whether the resource type is supported,
- whether the signed-in user owns the resource by tag,
- cleanup compartment OCID,
- runtime IAM policies,
- application logs.

### Image pull fails

Check:

- OCIR repository path,
- image tag,
- `imagePullSecrets`,
- OCIR username format,
- auth token validity,
- node egress to OCIR.

### Helm install fails

Run:

```bash
helm template oci-management-portal deploy/helm/oci-management-portal -f my-values.yaml
kubectl get events -n "${APP_NAMESPACE}" --sort-by=.lastTimestamp
kubectl describe pod -n "${APP_NAMESPACE}" -l app.kubernetes.io/instance=oci-management-portal
```

Check values for missing image, config, secret, service account, or session backend settings.

## Useful References

- Main project overview and architecture: [README.md](README.md)
- Local/manual deployment details: [LOCAL_DEPLOYMENT_GUIDE.md](LOCAL_DEPLOYMENT_GUIDE.md)
- Terraform stack notes: [deploy/terraform/README.md](deploy/terraform/README.md)
- Helm chart guide: [deploy/helm/oci-management-portal/README.md](deploy/helm/oci-management-portal/README.md)
- Helm runbook: [deploy/helm/oci-management-portal/RUNBOOK.md](deploy/helm/oci-management-portal/RUNBOOK.md)
- Cloud Shell Helm flow: [deploy/helm/oci-management-portal/CLOUDSHELL.md](deploy/helm/oci-management-portal/CLOUDSHELL.md)
- Runtime environment example: [sample.env](sample.env)
- Helm values example: [deploy/helm/oci-management-portal/my-values.yaml](deploy/helm/oci-management-portal/my-values.yaml)
