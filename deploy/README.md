# Deploy Terraform (OCI OKE)

This directory contains Terraform configuration for deploying an OCI OKE cluster with:

- VCN-native pod networking
- Four subnets (API endpoint, worker nodes, pods, load balancer)
- NSG-first security model (including SSH source NSG)
- Optional auto-selection of latest OKE platform image by selected node shape

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
