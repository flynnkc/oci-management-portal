locals {
  endpoint_subnet_id = oci_core_subnet.subnet_api_public.id

  # Infer node architecture from shape family for OKE node source filtering.
  node_pool_os_arch = can(regex("^VM\\.Standard\\.A", var.node_shape)) ? "aarch64" : "amd64"

  selected_node_image_id = var.use_latest_platform_oke_image ? local.latest_platform_oke_image_id : var.node_image_ocid
}

locals {
  # Pick the first OKE-supported image source for this k8s version/arch.
  latest_platform_oke_image_id = try([
    for s in data.oci_containerengine_node_pool_option.oke.sources : s.image_id
    if s.source_type == "IMAGE"
  ][0], null)
}

# Pick "All .* Services In Oracle Services Network"
locals {
  osn_service = one([
    for s in data.oci_core_services.all.services :
    s if can(regex("All .* Services In Oracle Services Network", s.name))
  ])

  osn_service_id   = local.osn_service.id
  osn_service_cidr = local.osn_service.cidr_block
}