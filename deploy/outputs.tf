output "vcn_id" {
  description = "OCID of the OKE VCN."
  value       = oci_core_vcn.vcn.id
}

output "cluster_id" {
  description = "OCID of the OKE cluster."
  value       = oci_containerengine_cluster.cluster.id
}

output "node_pool_id" {
  description = "OCID of the default OKE node pool."
  value       = oci_containerengine_node_pool.np1.id
}

output "subnet_ids" {
  description = "Subnet OCIDs used by OKE (api, nodes, pods, load balancer)."
  value = {
    api_server   = oci_core_subnet.subnet_api_public.id
    worker_nodes = oci_core_subnet.subnet_nodes_private.id
    pods         = oci_core_subnet.subnet_pods_private.id
    loadbalancer = oci_core_subnet.subnet_lb_public.id
  }
}

output "nsg_ids" {
  description = "NSG OCIDs used by OKE and SSH source trust model."
  value = {
    endpoint   = oci_core_network_security_group.nsg_endpoint.id
    nodes      = oci_core_network_security_group.nsg_nodes.id
    pods       = oci_core_network_security_group.nsg_pods.id
    lb         = oci_core_network_security_group.nsg_lb.id
    ssh_source = oci_core_network_security_group.nsg_ssh.id
  }
}
