# Cloud Shell Deploy Runbook

Use this from OCI Cloud Shell after your OKE kubeconfig is active and the project files are available in Cloud Shell.

## 1. Set Deployment Variables

```bash
export REGION="us-ashburn-1"
export REGISTRY="ocir.${REGION}.oci.oraclecloud.com"
export OCIR_NAMESPACE="$(oci os ns get --query data --raw-output)"
export REPO_NAME="oci-management-portal"
export IMAGE_TAG="$(date +%Y%m%d%H%M)"
export IMAGE_REPOSITORY="${REGISTRY}/${OCIR_NAMESPACE}/${REPO_NAME}"
export IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
export APP_NAMESPACE="oci-management-portal"
```

Set the compartment where the OCIR repository should be created:

```bash
export COMPARTMENT_OCID="<your-compartment-ocid>"
```

## 2. Create the OCIR Repository

```bash
oci artifacts container repository create \
  --display-name "${REPO_NAME}" \
  --compartment-id "${COMPARTMENT_OCID}"
```

If the repository already exists, continue to the next step.

## 3. Log In to OCIR

Generate an OCI auth token in the Console under your user profile, then run:

```bash
read -r -p "OCIR username, for example namespace/domain/user@example.com: " OCIR_USERNAME
read -r -s -p "OCIR auth token: " OCIR_AUTH_TOKEN
echo
printf '%s' "${OCIR_AUTH_TOKEN}" | docker login "${REGISTRY}" \
  --username "${OCIR_USERNAME}" \
  --password-stdin
```

For local OCI users, the username is usually:

```text
<tenancy-namespace>/<username>
```

For federated users, the username is usually:

```text
<tenancy-namespace>/<domain-name>/<username>
```

## 4. Build and Push the Application Image

Run this from the project root where the `Dockerfile` exists:

```bash
docker build -t "${REPO_NAME}:local" .
docker tag "${REPO_NAME}:local" "${IMAGE}"
docker push "${IMAGE}"
```

## 5. Create Kubernetes Secrets

Create the application namespace:

```bash
kubectl create namespace "${APP_NAMESPACE}"
```

If the namespace already exists, continue.

Create the image pull secret:

```bash
kubectl create secret docker-registry ocirsecret \
  --namespace "${APP_NAMESPACE}" \
  --docker-server="${REGISTRY}" \
  --docker-username="${OCIR_USERNAME}" \
  --docker-password="${OCIR_AUTH_TOKEN}" \
  --docker-email="unused@example.com"
```

Create the app secret:

```bash
read -r -s -p "OIDC client secret: " OIDC_CLIENT_SECRET
echo
kubectl create secret generic oci-management-portal-secrets \
  --namespace "${APP_NAMESPACE}" \
  --from-literal=OCI_MGMT_DASH_CLIENT_SECRET="${OIDC_CLIENT_SECRET}"
```

## 6. Create Helm Values

Replace the placeholder values before installing:

```bash
cat > my-values.yaml <<EOF
image:
  repository: ${IMAGE_REPOSITORY}
  tag: "${IMAGE_TAG}"
  pullPolicy: IfNotPresent

imagePullSecrets:
  - name: ocirsecret

config:
  appUri: "http://replace-with-load-balancer-or-ingress-url"
  proxy: "true"
  tagNamespace: "Management"
  tagKey: "Creator"
  filterNamespace: "Project"
  filterKey: "Expires"
  cleanupCompartment: "ocid1.compartment.oc1..replace_me"
  authType: "instance_principal"
  idmEndpoint: "https://idcs-replace.identity.oraclecloud.com:443"
  clientId: "replace-client-id"
  sessionBackend: "filesystem"

secret:
  create: false
  existingSecret: oci-management-portal-secrets

service:
  type: LoadBalancer
  port: 80
EOF
```

Edit `my-values.yaml` and replace all placeholder values:

```bash
nano my-values.yaml
```

## 7. Deploy with Helm

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace "${APP_NAMESPACE}" \
  -f my-values.yaml
```

## 8. Verify

```bash
kubectl get pods -n "${APP_NAMESPACE}"
kubectl get svc -n "${APP_NAMESPACE}"
kubectl logs -n "${APP_NAMESPACE}" deploy/oci-management-portal
```

If the pod is not ready, inspect events and logs:

```bash
kubectl describe pod -n "${APP_NAMESPACE}" -l app.kubernetes.io/instance=oci-management-portal
kubectl get events -n "${APP_NAMESPACE}" --sort-by=.lastTimestamp
```

The chart defaults to `instance_principal` auth. Your OKE worker node instance or node compartment must be included in an OCI dynamic group with permission to read and manage the OCI resources this app uses.
