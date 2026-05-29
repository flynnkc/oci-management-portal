data "oci_identity_availability_domains" "ads" {
  # Availability domains are listed at the TENANCY level.
  compartment_id = var.tenancy_ocid
}

data "oci_core_services" "all" {}

data "oci_containerengine_node_pool_option" "oke" {
  compartment_id      = var.compartment_ocid
  node_pool_option_id = oci_containerengine_cluster.cluster.id

  # Restrict source images to the same Kubernetes version used by the node pool.
  node_pool_k8s_version = var.k8s_version

  # Keep image architecture aligned with selected node shape family.
  node_pool_os_arch = local.node_pool_os_arch
}
