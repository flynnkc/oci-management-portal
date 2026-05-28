#### Virtual Cloud Network ####
resource "oci_core_vcn" "vcn" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "${var.label}-vcn"
  dns_label      = "okevcn"
}

resource "oci_core_default_security_list" "default_sl" {
  manage_default_resource_id = oci_core_vcn.vcn.default_security_list_id
  display_name               = "${var.label}-default-security-list"
}

#### Gateways ####
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

resource "oci_core_service_gateway" "sgw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-sgw"

  services {
    service_id = local.osn_service_id
  }
}

#### Route Tables ####
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

#### Subnets ####
resource "oci_core_subnet" "subnet_lb_public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.10.0/24"
  display_name               = "${var.label}-subnet-lb-public"
  dns_label                  = "load"
  route_table_id             = oci_core_route_table.rt_public.id
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_subnet" "subnet_nodes_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.20.0/24"
  display_name               = "${var.label}-subnet-worker-nodes-private"
  dns_label                  = "nodes"
  route_table_id             = oci_core_route_table.rt_private.id
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_pods_private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.30.0/23"
  display_name               = "${var.label}-subnet-pods-private"
  dns_label                  = "pods"
  route_table_id             = oci_core_route_table.rt_private.id
  prohibit_public_ip_on_vnic = true
}

resource "oci_core_subnet" "subnet_api_public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vcn.id
  cidr_block                 = "10.0.40.0/24"
  display_name               = "${var.label}-subnet-api-server-public"
  dns_label                  = "apiserver"
  route_table_id             = oci_core_route_table.rt_public.id
  prohibit_public_ip_on_vnic = false
}

#### Network Security Groups ####
resource "oci_core_network_security_group" "nsg_nodes" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-worker-nodes"
}

resource "oci_core_network_security_group" "nsg_endpoint" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-api-endpoint"
}

resource "oci_core_network_security_group" "nsg_pods" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-pods"
}

resource "oci_core_network_security_group" "nsg_lb" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-lb"
}

resource "oci_core_network_security_group" "nsg_ssh" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vcn.id
  display_name   = "${var.label}-nsg-ssh-source"
}

#### Network Security Group Rules ####

### API Server Rules ###

## API Ingress ##

# Allow nodes to reach Kubernetes API endpoint for cluster management
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_control_nodes" {
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

# Allow kubelet to reach Kubernetes API endpoint
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_kubelet_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id

  tcp_options {
    destination_port_range {
      min = 12250
      max = 12250
    }
  }
}

# Path Discovery
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_icmp_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "1" # ICMP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id

  icmp_options {
    type = 3
    code = 4
  }
}

# Allow pods to reach Kubernetes API endpoint for cluster management
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_control_pods" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_pods.id

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

# Allow pods to reach Kubernetes API endpoint for cluster management
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_kubelet_pods" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_pods.id

  tcp_options {
    destination_port_range {
      min = 12250
      max = 12250
    }
  }
}

# Optional external kubectl access to API endpoint (enabled by variable gate)
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_external" {
  count = var.enable_external_kubectl_access ? 1 : 0

  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "CIDR_BLOCK"
  source                    = try(trimspace(var.external_kubectl_access_cidr), "")

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }

  lifecycle {
    precondition {
      condition = (
        !var.enable_external_kubectl_access ||
        (
          var.external_kubectl_access_cidr != null &&
          try(trimspace(var.external_kubectl_access_cidr), "") != "" &&
          can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/([0-9]|[1-2][0-9]|3[0-2])$", try(trimspace(var.external_kubectl_access_cidr), ""))) &&
          can(cidrhost(try(trimspace(var.external_kubectl_access_cidr), ""), 0))
        )
      )
      error_message = "When enable_external_kubectl_access is true, external_kubectl_access_cidr must be set to a valid CIDR (for example, 203.0.113.0/24)."
    }
  }
}

# Baseline client kubectl access from trusted source NSG (for example, bastion/private endpoint)
resource "oci_core_network_security_group_security_rule" "endpoint_api_ingress_from_ssh_source" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_ssh.id

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

## API Egress ##

# Allow all traffic to OCI services
resource "oci_core_network_security_group_security_rule" "endpoint_api_egress_services" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "SERVICE_CIDR_BLOCK"
  destination               = local.osn_service_cidr

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

/*
# Allow API endpoint access to OCI public APIs over HTTPS
resource "oci_core_network_security_group_security_rule" "endpoint_api_egress_https_internet" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}
*/

# Allow API server communication to worker nodes
resource "oci_core_network_security_group_security_rule" "endpoint_api_egress_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  tcp_options {
    destination_port_range {
      min = 10250
      max = 10250
    }
  }
}

# Path Discovery
resource "oci_core_network_security_group_security_rule" "endpoint_api_egress_icmp_nodes" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "1" # ICMP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  icmp_options {
    type = 3
    code = 4
  }
}

# Allow all traffic to pods
resource "oci_core_network_security_group_security_rule" "endpoint_api_egress_pods" {
  network_security_group_id = oci_core_network_security_group.nsg_endpoint.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_pods.id
}

### Node Rules ###

## Node Ingress ##

# Allow control plane endpoint to reach kubelet on worker nodes during registration/operations
resource "oci_core_network_security_group_security_rule" "nodes_kubelet_ingress_from_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 10250
      max = 10250
    }
  }
}

# Path Discovery
resource "oci_core_network_security_group_security_rule" "nodes_ingress_icmp" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "1" # ICMP
  source_type               = "CIDR_BLOCK"
  source                    = "0.0.0.0/0"

  icmp_options {
    type = 3
    code = 4
  }
}

# SSH access to worker nodes is sourced from nsg_ssh
# (attach nsg_ssh to your bastion host/private endpoint VNIC)
resource "oci_core_network_security_group_security_rule" "nodes_ssh_ingress_from_ssh_source" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_ssh.id

  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

# Node-to-node (same NSG) allow all
resource "oci_core_network_security_group_security_rule" "nodes_intra_ingress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_nodes.id
}

# Allow endpoint control-plane bootstrap traffic to worker nodes
resource "oci_core_network_security_group_security_rule" "nodes_bootstrap_ingress_from_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 12250
      max = 12250
    }
  }
}

# Node-to-pods allow all
resource "oci_core_network_security_group_security_rule" "nodes_pod_ingress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_pods.id
}

# Allow OCI load balancer or network load balancer to communicate with kube-proxy on worker nodes
resource "oci_core_network_security_group_security_rule" "node_ingress_proxy_tcp" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_lb.id

  tcp_options {
    destination_port_range {
      min = 10256
      max = 10256
    }
  }
}

# Allow OCI load balancer or network load balancer to communicate with kube-proxy on worker nodes
resource "oci_core_network_security_group_security_rule" "node_ingress_proxy_udp" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "INGRESS"
  protocol                  = "17" # UDP
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_lb.id

  udp_options {
    destination_port_range {
      min = 10256
      max = 10256
    }
  }
}

## Node Egress ##

# Node-to-node (same NSG) allow all
resource "oci_core_network_security_group_security_rule" "nodes_intra_egress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id
}

# Node-to-node (same NSG) allow all
resource "oci_core_network_security_group_security_rule" "nodes_pod_egress" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_pods.id
}

# Path Discovery
resource "oci_core_network_security_group_security_rule" "nodes_egress_icmp" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "1" # ICMP
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"

  icmp_options {
    type = 3
    code = 4
  }
}

# Allow all traffic to OCI services
resource "oci_core_network_security_group_security_rule" "node_egress_services" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "SERVICE_CIDR_BLOCK"
  destination               = local.osn_service_cidr
}

# Node to API Server communication
resource "oci_core_network_security_group_security_rule" "node_egress_api_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

# Node to API Server communication
resource "oci_core_network_security_group_security_rule" "node_egress_kubelet_api_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 12250
      max = 12250
    }
  }
}

# Node to internet communication
resource "oci_core_network_security_group_security_rule" "node_egress_internet" {
  network_security_group_id = oci_core_network_security_group.nsg_nodes.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

### Pod Rules ###

## Pod Ingress ##

resource "oci_core_network_security_group_security_rule" "pods_ingress_api_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source_type               = "NETWORK_SECURITY_GROUP"
  source                    = oci_core_network_security_group.nsg_endpoint.id
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

## Pod Egress ##

# Pod-to-pod egress (Same NSG)
resource "oci_core_network_security_group_security_rule" "pods_egress_pod" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_pods.id
}

# Allow discovery traffic to OCI services
resource "oci_core_network_security_group_security_rule" "pods_egress_icmp_services" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "1" # ICMP
  destination_type          = "SERVICE_CIDR_BLOCK"
  destination               = local.osn_service_cidr

  icmp_options {
    type = 3
    code = 4
  }
}

# Allow TCP traffic to OCI services
resource "oci_core_network_security_group_security_rule" "pods_egress_services" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "SERVICE_CIDR_BLOCK"
  destination               = local.osn_service_cidr
}

# Pod to API Server communication
resource "oci_core_network_security_group_security_rule" "pod_egress_api_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

# Pod to API Server communication
resource "oci_core_network_security_group_security_rule" "pod_egress_kubelet_api_endpoint" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_endpoint.id

  tcp_options {
    destination_port_range {
      min = 12250
      max = 12250
    }
  }
}

# Pod to Internet HTTPS communication
resource "oci_core_network_security_group_security_rule" "pod_egress_internet" {
  network_security_group_id = oci_core_network_security_group.nsg_pods.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

### Load Balancer Rules ###

## Load Balancer Ingress ##

resource "oci_core_network_security_group_security_rule" "lb_ingress_http" {
  count = var.enable_lb_http_ingress ? 1 : 0

  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "CIDR_BLOCK"
  source                    = try(trimspace(var.lb_ingress_source_cidr), "")

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
  source                    = try(trimspace(var.lb_ingress_source_cidr), "")

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

## Load Balancer Egress ##

resource "oci_core_network_security_group_security_rule" "lb_egress_tcp_highports" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  tcp_options {
    destination_port_range {
      min = 30000
      max = 32767
    }
  }
}

resource "oci_core_network_security_group_security_rule" "lb_egress_udp_highports" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "EGRESS"
  protocol                  = "17" # UDP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  udp_options {
    destination_port_range {
      min = 30000
      max = 32767
    }
  }
}

# Allow OCI load balancer or network load balancer to communicate with kube-proxy on worker nodes
resource "oci_core_network_security_group_security_rule" "lb_egress_udp_proxy" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "EGRESS"
  protocol                  = "17" # UDP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  udp_options {
    destination_port_range {
      min = 10256
      max = 10256
    }
  }
}

# Allow OCI load balancer or network load balancer to communicate with kube-proxy on worker nodes
resource "oci_core_network_security_group_security_rule" "lb_egress_tcp_proxy" {
  network_security_group_id = oci_core_network_security_group.nsg_lb.id
  direction                 = "EGRESS"
  protocol                  = "6" # TCP
  destination_type          = "NETWORK_SECURITY_GROUP"
  destination               = oci_core_network_security_group.nsg_nodes.id

  tcp_options {
    destination_port_range {
      min = 10256
      max = 10256
    }
  }
}
