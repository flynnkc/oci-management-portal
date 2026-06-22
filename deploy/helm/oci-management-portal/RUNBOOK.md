# OCI Management Portal OKE Deployment Runbook

This runbook deploys the OCI Management Portal to OKE using:

- OCIR for the application image
- Helm for Kubernetes manifests
- OCI instance principals through the OKE worker node identity
- OCI LoadBalancer service for browser access

It assumes the OKE cluster and node pool already exist and `kubectl` is configured in OCI Cloud Shell.

## 1. Configure Cloud Shell Kubeconfig

Open OCI Cloud Shell in the same region as the OKE cluster.

Set common variables:

```bash
export REGION="us-ashburn-1"
export CLUSTER_OCID="<cluster-ocid>"
```

Create or update kubeconfig for the cluster:

```bash
oci ce cluster create-kubeconfig \
  --cluster-id "$CLUSTER_OCID" \
  --file "$HOME/.kube/config" \
  --region "$REGION" \
  --token-version 2.0.0 \
  --kube-endpoint PUBLIC_ENDPOINT
```

If the cluster has only a private Kubernetes API endpoint, use:

```bash
oci ce cluster create-kubeconfig \
  --cluster-id "$CLUSTER_OCID" \
  --file "$HOME/.kube/config" \
  --region "$REGION" \
  --token-version 2.0.0 \
  --kube-endpoint PRIVATE_ENDPOINT
```

Set restrictive kubeconfig permissions:

```bash
chmod 600 "$HOME/.kube/config"
```

Verify the current context:

```bash
kubectl config current-context
```

## 2. Verify Cluster Access

```bash
kubectl get nodes
kubectl get pods -A
```

The worker node must be `Ready`.

If the node shows `NotReady`, describe it:

```bash
kubectl describe node <node-name>
```

If the backing OCI instance is stopped, start it:

```bash
export NODE="<node-name>"
export INSTANCE_OCID="$(kubectl get node "$NODE" -o jsonpath='{.spec.providerID}' | sed 's#oci://##')"

oci compute instance action \
  --instance-id "$INSTANCE_OCID" \
  --action START
```

## 3. Create A Dynamic Group For Worker Nodes

Instance principal auth does not require an Enhanced OKE cluster. It uses the OCI identity of the worker node instance.

Get the worker node instance OCID:

```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.providerID}{"\n"}{end}'
```

Set the instance OCID without the `oci://` prefix:

```bash
export INSTANCE_OCID="<worker-instance-ocid>"

oci compute instance get \
  --instance-id "$INSTANCE_OCID" \
  --query 'data."compartment-id"' \
  --raw-output
```

Create a dynamic group in OCI Console:

```text
Identity & Security -> Domains -> Default domain -> Dynamic groups
```

For a single worker node, use:

```text
instance.id = '<worker-instance-ocid>'
```

For a dedicated OKE node compartment, use a compartment rule so replacement nodes continue to match:

```text
instance.compartment.id = '<node-compartment-ocid>'
```

## 4. Add IAM Policies For Instance Principals

Add these policies for the dynamic group, replacing `<dynamic-group-name>` with the dynamic group created above.

Broad application access policy:

```text
Allow dynamic-group <dynamic-group-name> to manage all-resources in tenancy
```

Explicit compartment inspection policy used by app startup:

```text
Allow dynamic-group <dynamic-group-name> to inspect compartments in tenancy
```

Cost data policy used by the app:

```text
Allow dynamic-group <dynamic-group-name> to read usage-reports in tenancy
```

For production, reduce `manage all-resources` to the minimum resource families and compartments the portal should manage.

If you previously used workload principal policies, they are not required for instance principal auth.
The chart now defaults to `serviceAccount.automount=false` because instance principal auth does not need a Kubernetes service account token.
If you switch back to workload principal later, set `serviceAccount.automount=true`.

## 5. Set OCIR And Image Variables

Run from OCI Cloud Shell in the project root where `Dockerfile` exists.

```bash
export REGION="us-ashburn-1"
export REGISTRY="ocir.${REGION}.oci.oraclecloud.com"
export OCIR_NAMESPACE="$(oci os ns get --query data --raw-output)"
export REPO_NAME="oci-management-portal"
export IMAGE_REPOSITORY="${REGISTRY}/${OCIR_NAMESPACE}/${REPO_NAME}"
export IMAGE_TAG="$(date +%Y%m%d%H%M)"
export IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
export APP_NAMESPACE="oci-management-portal"
export COMPARTMENT_OCID="<compartment-ocid-for-ocir-repository>"
```

Create the OCIR repository if it does not already exist:

```bash
oci artifacts container repository create \
  --display-name "$REPO_NAME" \
  --compartment-id "$COMPARTMENT_OCID"
```

If the repository already exists, continue.

## 6. Log In To OCIR

Create an OCI auth token for your user in OCI Console. Use the auth token for Docker login, not your Console password.

```bash
read -r -p "OCIR username: " OCIR_USERNAME
read -r -s -p "OCIR auth token: " OCIR_AUTH_TOKEN
echo

printf '%s' "$OCIR_AUTH_TOKEN" | docker login "$REGISTRY" \
  --username "$OCIR_USERNAME" \
  --password-stdin
```

Example OCIR usernames:

```text
<tenancy-namespace>/<username>
<tenancy-namespace>/<identity-domain>/<username>
```

## 7. Build And Push The Image

Run from the project root:

```bash
docker build -t "${REPO_NAME}:local" .
docker tag "${REPO_NAME}:local" "$IMAGE"
docker push "$IMAGE"
```

If you rebuild after code changes, use a new tag:

```bash
export IMAGE_TAG="20260603-fix1"
export IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"

docker build -t "$IMAGE" .
docker push "$IMAGE"
```

## 8. Create Kubernetes Namespace And Secrets

```bash
kubectl create namespace "$APP_NAMESPACE"
```

If the namespace already exists, continue.

Create the OCIR image pull secret:

```bash
kubectl create secret docker-registry ocirsecret \
  --namespace "$APP_NAMESPACE" \
  --docker-server="$REGISTRY" \
  --docker-username="$OCIR_USERNAME" \
  --docker-password="$OCIR_AUTH_TOKEN" \
  --docker-email="unused@example.com"
```

Create the application OIDC client secret:

```bash
read -r -s -p "OIDC client secret: " OIDC_CLIENT_SECRET
echo

kubectl create secret generic oci-management-portal-secrets \
  --namespace "$APP_NAMESPACE" \
  --from-literal=OCI_MGMT_DASH_CLIENT_SECRET="$OIDC_CLIENT_SECRET"
```

If a secret already exists and must be replaced:

```bash
kubectl delete secret oci-management-portal-secrets -n "$APP_NAMESPACE"

kubectl create secret generic oci-management-portal-secrets \
  --namespace "$APP_NAMESPACE" \
  --from-literal=OCI_MGMT_DASH_CLIENT_SECRET="$OIDC_CLIENT_SECRET"
```

## 9. Create Helm Values

Create `my-values.yaml` in the project root:

```bash
cat > my-values.yaml <<EOF
image:
  repository: ${IMAGE_REPOSITORY}
  tag: "${IMAGE_TAG}"
  pullPolicy: IfNotPresent

imagePullSecrets:
  - name: ocirsecret

config:
  appUri: "http://placeholder"
  proxy: "true"
  tagNamespace: "Management"
  tagKey: "Creator"
  filterNamespace: "Project"
  filterKey: "Expires"
  cleanupCompartment: "<cleanup-compartment-ocid>"
  authType: "instance_principal"
  idmEndpoint: "<identity-domain-url>"
  clientId: "<oidc-client-id>"
  sessionBackend: "filesystem"

secret:
  create: false
  existingSecret: oci-management-portal-secrets

service:
  type: LoadBalancer
  port: 80
  annotations:
    oci.oraclecloud.com/load-balancer-type: "lb"
EOF
```

Edit placeholders:

```bash
nano my-values.yaml
```

Required values:

- `image.repository`
- `image.tag`
- `config.cleanupCompartment`
- `config.idmEndpoint`
- `config.clientId`
- `config.appUri`
- OIDC secret stored in `oci-management-portal-secrets`

## 10. Deploy With Helm

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace "$APP_NAMESPACE" \
  -f my-values.yaml
```

Watch rollout:

```bash
kubectl rollout status deployment/oci-management-portal -n "$APP_NAMESPACE"
kubectl get pods -n "$APP_NAMESPACE" -o wide
```

## 11. Get The LoadBalancer IP

```bash
kubectl get svc -n "$APP_NAMESPACE"
```

Wait until `EXTERNAL-IP` is populated.

```bash
kubectl get svc -n "$APP_NAMESPACE" -w
```

Update `my-values.yaml`:

```yaml
config:
  appUri: "http://<external-ip>"
  proxy: "true"
```

Apply the updated app URI:

```bash
helm upgrade --install oci-management-portal deploy/helm/oci-management-portal \
  --namespace "$APP_NAMESPACE" \
  -f my-values.yaml
```

## 12. Configure OCI Identity Domain Callback

If the confidential application is managed by Terraform, update `confidential_application_base_url` to the deployed portal URL and rerun `terraform apply`.

Terraform will register:

```text
http://<external-ip>/callback
```

If using HTTPS and DNS later, set `confidential_application_base_url` to the DNS URL so Terraform registers:

```text
https://<dns-name>/callback
```

If you are using a manually created confidential application instead, add the same callback URI in the OCI Identity Domain console.

## 13. Validate The App

Check pods:

```bash
kubectl get pods -n "$APP_NAMESPACE"
```

Check logs:

```bash
kubectl logs -n "$APP_NAMESPACE" deploy/oci-management-portal --tail=200
```

Health check:

```bash
curl -i "http://<external-ip>/health"
```

Open in browser:

```text
http://<external-ip>
```

## 14. Useful Troubleshooting

Check service events:

```bash
kubectl describe svc oci-management-portal -n "$APP_NAMESPACE"
kubectl get events -n "$APP_NAMESPACE" --sort-by=.lastTimestamp
```

Check pod events:

```bash
kubectl describe pod -n "$APP_NAMESPACE" -l app.kubernetes.io/instance=oci-management-portal
```

Check image in deployment:

```bash
kubectl get deploy oci-management-portal -n "$APP_NAMESPACE" \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Check region env vars:

```bash
kubectl get pod -n "$APP_NAMESPACE" \
  -l app.kubernetes.io/instance=oci-management-portal \
  -o jsonpath='{range .items[0].spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}'
```

If the node is `NotReady`:

```bash
kubectl describe node <node-name>
kubectl get node <node-name> -o jsonpath='{.spec.providerID}{"\n"}'
```

If needed, start the backing OCI compute instance:

```bash
export NODE="<node-name>"
export INSTANCE_OCID="$(kubectl get node "$NODE" -o jsonpath='{.spec.providerID}' | sed 's#oci://##')"

oci compute instance action \
  --instance-id "$INSTANCE_OCID" \
  --action START
```
