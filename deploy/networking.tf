resource "oci_core_vcn" "vcn" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "oke-flannel-vcn"
  dns_label      = "okeflnl"
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "igw"
  enabled        = true
}

resource "oci_core_nat_gateway" "nat" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "nat"
}

data "oci_core_services" "all" {}

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
  display_name   = "sgw"

  services {
    service_id = local.osn_service_id
  }
}

resource "oci_core_route_table" "rt_public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "rt-public"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
  }
}

resource "oci_core_route_table" "rt_private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "rt-private"

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
  display_name   = "nsg-oke-nodes"
}

resource "oci_core_network_security_group" "nsg_endpoint" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "nsg-oke-endpoint"
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

# Flannel VXLAN overlay (UDP 4789) node-to-node (if you use vxlan backend)
resource "oci_core_network_security_group_security_rule" "flannel_vxlan_ingress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "17" # UDP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id

  udp_options {
    destination_port_range {
      min = 4789
      max = 4789
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

resource "oci_core_security_list" "sl_public_lb" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "sl-public-lb"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_security_list" "sl_private_nodes" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "sl-private-nodes"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "all"
    source   = "10.0.0.0/16"
  }
}

resource "oci_core_subnet" "subnet_lb_public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.10.0/24"
  display_name               = "subnet-lb-public"
  dns_label                  = "lbpub"
  route_table_id             = oci_core_route_table.rt_public.id
  security_list_ids          = [oci_core_security_list.sl_public_lb.id]
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_subnet" "subnet_nodes_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.20.0/24"
  display_name               = "subnet-nodes-private"
  dns_label                  = "nodep"
  route_table_id             = oci_core_route_table.rt_private.id
  security_list_ids          = [oci_core_security_list.sl_private_nodes.id]
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_addl_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.30.0/24"
  display_name               = "subnet-addl-private"
  dns_label                  = "addlp"
  route_table_id             = oci_core_route_table.rt_private.id
  security_list_ids          = [oci_core_security_list.sl_private_nodes.id]
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_endpoint_private" {
  count                      = var.create_endpoint_subnet ? 1 : 0
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.5.0/24"
  display_name               = "subnet-endpoint-private"
  dns_label                  = "endpt"
  route_table_id             = oci_core_route_table.rt_private.id
  security_list_ids          = [oci_core_security_list.sl_private_nodes.id]
  prohibit_public_ip_on_vnic = true
}
