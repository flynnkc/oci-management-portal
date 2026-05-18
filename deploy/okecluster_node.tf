resource "oci_containerengine_cluster" "cluster" {
  compartment_id     = var.compartment_ocid
  name               = "${var.label}-cluster"
  kubernetes_version = var.k8s_version
  vcn_id             = oci_core_vcn.vcn.id

  endpoint_config {
    is_public_ip_enabled = false
    subnet_id            = local.endpoint_subnet_id

    # Attach endpoint NSG so the 6443 rule (from nodes NSG to endpoint NSG) is actually enforced
    nsg_ids = [oci_core_network_security_group.nsg_endpoint.id]
  }

  options {
    service_lb_subnet_ids = [oci_core_subnet.subnet_lb_public.id]

    service_lb_config {
      backend_nsg_ids = [oci_core_network_security_group.nsg_lb.id]
    }

    kubernetes_network_config {
      pods_cidr     = "10.244.0.0/16"
      services_cidr = "10.96.0.0/16"
    }
  }
}

resource "oci_containerengine_node_pool" "np1" {
  cluster_id         = oci_containerengine_cluster.cluster.id
  compartment_id     = var.compartment_ocid
  name               = "${var.label}-np1"
  kubernetes_version = var.k8s_version

  node_config_details {
    size    = var.nodepool_size
    nsg_ids = [oci_core_network_security_group.nsg_nodes.id]

    placement_configs {
      availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
      subnet_id           = oci_core_subnet.subnet_nodes_private.id
    }

    node_pool_pod_network_option_details {
      cni_type          = "OCI_VCN_IP_NATIVE"
      pod_subnet_ids    = [oci_core_subnet.subnet_pods_private.id]
      pod_nsg_ids       = [oci_core_network_security_group.nsg_pods.id]
      max_pods_per_node = 31
    }
  }

  ssh_public_key = var.worker_ssh_public_key

  node_shape = var.node_shape

  dynamic "node_shape_config" {
    for_each = var.node_shape == "VM.Standard.E4.Flex" ? [1] : []
    content {
      ocpus         = var.node_ocpus
      memory_in_gbs = var.node_memory
    }
  }

  node_source_details {
    source_type = "IMAGE"
    image_id    = local.selected_node_image_id
  }

  lifecycle {
    precondition {
      condition     = var.use_latest_platform_oke_image || try(trimspace(var.node_image_ocid) != "", false)
      error_message = "node_image_ocid must be set when use_latest_platform_oke_image is false."
    }

    precondition {
      condition     = !var.use_latest_platform_oke_image || local.latest_platform_oke_image_id != null
      error_message = "No OKE platform image was found for the selected node_shape. Update node_shape or set use_latest_platform_oke_image=false and provide node_image_ocid."
    }
  }
}