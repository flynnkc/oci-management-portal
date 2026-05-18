locals {
  endpoint_subnet_id = oci_core_subnet.subnet_api_private.id

  selected_node_image_id = var.use_latest_platform_oke_image ? local.latest_platform_oke_image_id : var.node_image_ocid
}

data "oci_core_images" "platform_oke_images" {
  compartment_id = var.compartment_ocid

  filter {
    name   = "display_name"
    regex  = true
    values = ["^Oracle-Linux-.*-OKE-.*"]
  }

  operating_system = "Oracle Linux"
  shape            = var.node_shape
  sort_by          = "TIMECREATED"
  sort_order       = "DESC"
  state            = "AVAILABLE"
}

locals {
  latest_platform_oke_image_id = one(data.oci_core_images.platform_oke_images.images).id
}