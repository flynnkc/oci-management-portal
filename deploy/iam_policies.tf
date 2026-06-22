resource "oci_identity_policy" "oke_cluster_operations" {
  provider = oci.home

  count = var.enable_oke_iam_policies ? 1 : 0

  compartment_id = var.compartment_ocid
  name           = "${var.label}-${var.oke_policy_name}"
  description    = "Baseline IAM policy for OKE cluster and node pool operations"

  statements = [
    "Allow service OKE to manage cluster-family in compartment id ${var.compartment_ocid}",
    "Allow service OKE to manage instance-family in compartment id ${var.compartment_ocid}",
    "Allow service OKE to use virtual-network-family in compartment id ${var.compartment_ocid}",
    "Allow service OKE to manage volume-family in compartment id ${var.compartment_ocid}",
    "Allow any-user to manage virtual-network-family in compartment id ${var.compartment_ocid} where all { request.principal.type = 'cluster', request.principal.compartment.id = '${var.compartment_ocid}' }"
  ]
}
