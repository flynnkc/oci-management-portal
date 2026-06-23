# Deploy Terraform (OCI OKE)

This directory contains Terraform configuration for deploying an OCI OKE cluster with:

- OCI VCN IP Native pod networking
- Subnets for the private API endpoint, worker nodes, additional private workloads, and the public load balancer
- Node and API endpoint NSGs, plus subnet security lists
- Optional auto-selection of latest OKE platform image by selected node shape
- Private OKE API endpoint
- OCI Identity Domain confidential application for portal OIDC login

## File layout

- `versions.tf` - Terraform and OCI provider requirements
- `providers.tf` - OCI provider configuration
- `variables.tf` - Input variables and validations
- `data.tf` - Data sources (ADs, region/home-region lookup, OSN services, OKE platform images)
- `locals.tf` - Derived values and selection logic
- `networking.tf` - VCN, gateways, route tables, NSGs, subnets
- `okecluster_node.tf` - OKE cluster and node pool resources
- `confidential_application.tf` - OCI Identity Domain confidential application
- `outputs.tf` - Identity Domain and confidential application outputs for Helm configuration
- `schema.yaml` - OCI Resource Manager UI schema

## Image selection behavior

- `use_latest_platform_oke_image = true` (default):
  - Uses latest Oracle Linux OKE platform image compatible with `node_shape`.
- `use_latest_platform_oke_image = false`:
  - Uses explicit `node_image_ocid`.

## Notes

- Attach `nsg_ssh_source` to your bastion/private endpoint VNIC to permit SSH (22) into worker nodes.
- Keep `schema.yaml` aligned with variables if you modify inputs.

## Confidential application

Select an existing OCI Identity Domain with `identity_domain_id`. Terraform creates an OIDC confidential application in that domain using the custom web application template.
Set `confidential_application_name` to the required OAuth client ID value that the Helm chart will use as `config.clientId`.

By default, Terraform registers `${confidential_application_base_url}/callback` as the redirect URI and `${confidential_application_base_url}` as the post-logout redirect URI. After apply, use these outputs when configuring the Helm chart:

- `identity_domain_endpoint` -> `config.idmEndpoint`
- `confidential_application_client_id` -> `config.clientId`
- `confidential_application_client_secret` -> `secret.clientSecret`

Terraform enables the `authorization_code` and `client_credentials` OAuth grants for the confidential application.
It also always enables HTTP redirect URLs, bypasses user consent, enables force delete for stack destroy, and configures the OAuth client operation as `introspect`.

If the application receives a new public load balancer URL after Helm deployment, update `confidential_application_base_url` (or set explicit redirect URI variables) and rerun `terraform apply` so the Identity Domain application callback matches the deployed URL.

## Network architecture

- **VCN CIDR**: `10.0.0.0/16`
- **Subnets**:
  - API endpoint subnet: private (`subnet_endpoint_private`, `10.0.5.0/24`)
  - Load balancer subnet: public (`subnet_lb_public`, `10.0.10.0/24`)
  - Worker nodes subnet: private (`subnet_nodes_private`, `10.0.20.0/24`)
  - Additional private subnet: private (`subnet_addl_private`, `10.0.30.0/24`)
- **Route tables**:
  - Public route table -> Internet Gateway (`0.0.0.0/0`)
  - Private route table -> NAT Gateway (`0.0.0.0/0`) + Service Gateway (`All <region> Services in Oracle Services Network`)

## Security and exposure controls

- **OKE API endpoint exposure**: private endpoint protected by `nsg_endpoint`.
- **Load balancer ingress**: public load balancer subnet security list allows HTTP (80) and HTTPS (443).
- **Worker networking**: `nsg_nodes` is attached to worker nodes and pods created through OCI VCN IP Native networking.
