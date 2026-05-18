data "oci_identity_availability_domains" "ads" {
  # Availability domains are listed at the TENANCY level.
  compartment_id = var.tenancy_ocid
}

data "oci_core_services" "all" {}

data "oci_core_images" "platform_oke_images" {
  # Platform images are published at tenancy scope.
  compartment_id = var.tenancy_ocid

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
