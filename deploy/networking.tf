resource "oci_core_vcn" "vcn" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "${var.label}-vcn"
  dns_label      = "okeflnl"
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-igw"
  enabled        = true
}

resource "oci_core_nat_gateway" "nat" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nat"
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

resource "oci_core_service_gateway" "sgw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-sgw"

  services {
    service_id = local.osn_service_id
  }
}

resource "oci_core_route_table" "rt_public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-rt-public"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
  }
}

resource "oci_core_route_table" "rt_private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-rt-private"

  # Internet egress from private subnets
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.nat.id
  }

  # OCI services via SGW (Object Storage, etc.)
  route_rules {
    destination       = local.osn_service_cidr
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.sgw.id
  }
}

resource "oci_core_network_security_group" "nsg_nodes" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-oke-nodes"
}

resource "oci_core_network_security_group" "nsg_endpoint" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-oke-endpoint"
}

resource "oci_core_network_security_group" "nsg_pods" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-oke-pods"
}

resource "oci_core_network_security_group" "nsg_lb" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-oke-lb"
}

resource "oci_core_network_security_group" "nsg_ssh_source" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-ssh-source"
}

# IMPORTANT: allow node egress (required when node pool attaches this NSG)
resource "oci_core_network_security_group_security_rule" "nodes_egress_all" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
}

# Optional but recommended: allow endpoint egress
resource "oci_core_network_security_group_security_rule" "endpoint_egress_all" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
}

# Node-to-node (same NSG) allow all (simple baseline; tighten as needed)
resource "oci_core_network_security_group_security_rule" "nodes_intra_ingress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id
}

# SSH access to worker nodes is sourced from nsg_ssh_source
# (attach nsg_ssh_source to your bastion host/private endpoint VNIC)
resource "oci_core_network_security_group_security_rule" "nodes_ssh_ingress_from_ssh_source" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_ssh_source.id

  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

# Allow nodes to reach Kubernetes API endpoint (private endpoint)
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_from_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

resource "oci_core_network_security_group_security_rule" "pods_egress_all" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
}

resource "oci_core_network_security_group_security_rule" "pods_ingress_from_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id
}

resource "oci_core_network_security_group_security_rule" "pods_ingress_from_pods" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_pods.id
}

resource "oci_core_network_security_group_security_rule" "lb_egress_all" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
}

resource "oci_core_network_security_group_security_rule" "lb_ingress_http" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "CIDR_BLOCK"
  source                    = "0.0.0.0/0"

  tcp_options {
    destination_port_range {
      min = 80
      max = 80
    }
  }
}

resource "oci_core_network_security_group_security_rule" "lb_ingress_https" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "CIDR_BLOCK"
  source                    = "0.0.0.0/0"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_subnet" "subnet_lb_public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.10.0/24"
  display_name               = "${var.label}-subnet-lb-public"
  dns_label                  = "lbpub"
  route_table_id             = oci_core_route_table.rt_public.id
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_subnet" "subnet_nodes_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.20.0/24"
  display_name               = "${var.label}-subnet-worker-nodes-private"
  dns_label                  = "nodep"
  route_table_id             = oci_core_route_table.rt_private.id
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_pods_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.30.0/24"
  display_name               = "${var.label}-subnet-pods-private"
  dns_label                  = "addlp"
  route_table_id             = oci_core_route_table.rt_private.id
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_api_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.5.0/24"
  display_name               = "${var.label}-subnet-api-server-private"
  dns_label                  = "endpt"
  route_table_id             = oci_core_route_table.rt_private.id
  prohibit_public_ip_on_vnic = true
}