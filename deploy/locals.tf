locals {
  endpoint_subnet_id = var.create_endpoint_subnet ? oci_core_subnet.subnet_endpoint_private[0].id : oci_core_subnet.subnet_nodes_private.id
}