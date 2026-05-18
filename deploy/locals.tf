locals {
  endpoint_subnet_id = oci_core_subnet.subnet_api_private.id

  selected_node_image_id = var.use_latest_platform_oke_image ? local.latest_platform_oke_image_id : var.node_image_ocid
}

locals {
  # Images are already sorted newest-first; pick first match safely.
  latest_platform_oke_image_id = try(data.oci_core_images.platform_oke_images.images[0].id, null)
}