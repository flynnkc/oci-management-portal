data "oci_identity_availability_domains" "ads" {
  # Availability domains are listed at the TENANCY level.
  compartment_id = var.tenancy_ocid
}

data "oci_identity_regions" "all" {}

data "oci_identity_tenancy" "tenancy" {
  tenancy_id = var.tenancy_ocid
}

data "oci_containerengine_cluster_option" "all" {
  compartment_id                 = var.compartment_ocid
  cluster_option_id              = "all"
  should_list_all_patch_versions = true
}

data "oci_containerengine_node_pool_option" "oke" {
  compartment_id      = var.compartment_ocid
  node_pool_option_id = oci_containerengine_cluster.cluster.id

  # Restrict source images to the same Kubernetes version used by the node pool.
  node_pool_k8s_version = local.effective_k8s_version

  # Keep image architecture aligned with selected node shape family.
  node_pool_os_arch = local.node_pool_os_arch
}
