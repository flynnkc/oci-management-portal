# Deploy Terraform (OCI OKE)

This directory contains Terraform configuration for deploying an OCI OKE cluster with:

- VCN-native pod networking
- Four subnets (API endpoint, worker nodes, pods, load balancer)
- NSG-first security model (including SSH source NSG)
- Optional auto-selection of latest OKE platform image by selected node shape
- Public OKE API endpoint (ephemeral public IP) on the API endpoint subnet
- Configurable load balancer ingress CIDR, with optional HTTP enablement

## File layout

- `versions.tf` - Terraform and provider requirements
- `providers.tf` - OCI provider configuration
- `variables.tf` - Input variables and validations
- `data.tf` - Data sources (ADs, OSN services, OKE platform images)
- `locals.tf` - Derived values and selection logic
- `networking.tf` - VCN, gateways, route tables, NSGs, subnets
- `okecluster_node.tf` - OKE cluster and node pool resources
- `outputs.tf` - Useful OCID outputs
- `schema.yaml` - OCI Resource Manager UI schema

## Image selection behavior

- `use_latest_platform_oke_image = true` (default):
  - Uses latest Oracle Linux OKE platform image compatible with `node_shape`.
- `use_latest_platform_oke_image = false`:
  - Uses explicit `node_image_ocid`.

## Notes

- Attach `nsg_ssh_source` to your bastion/private endpoint VNIC to permit SSH (22) into worker nodes.
- Keep `schema.yaml` aligned with variables if you modify inputs.

## Network architecture (OKE-aligned)

- **VCN CIDR**: `10.0.0.0/16`
- **Subnets**:
  - API endpoint subnet: public (`subnet_api_public`, `10.0.40.0/24`)
  - Worker nodes subnet: private (`subnet_nodes_private`, `10.0.20.0/24`)
  - Pods subnet: private (`subnet_pods_private`, `10.0.30.0/23`)
  - Load balancer subnet: public (`subnet_lb_public`, `10.0.10.0/24`)
- **Route tables**:
  - Public route table -> Internet Gateway (`0.0.0.0/0`)
  - Private route table -> NAT Gateway (`0.0.0.0/0`) + Service Gateway (`All <region> Services in Oracle Services Network`)

## Security and exposure controls

- **OKE API endpoint exposure**:
  - Endpoint is public and receives an ephemeral public IP from OCI.
  - Optional external `kubectl` ingress is controlled by:
    - `enable_external_kubectl_access`
    - `external_kubectl_access_cidr`
- **Load balancer ingress**:
  - HTTPS (443) is controlled by `lb_ingress_source_cidr`.
  - HTTP (80) is disabled by default and can be enabled with `enable_lb_http_ingress`.
- **Egress hardening**:
  - Node internet egress is restricted to TCP/443.
  - Broad pod egress-all rule removed; pod internet egress remains explicit TCP/443.
