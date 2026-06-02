variable "tenancy_ocid" {
  description = "OCID of the tenancy hosting the deployment"
  type        = string
}

variable "user_ocid" {
  description = "OCID of the user or resource principal running Terraform (required for CLI runs)"
  type        = string
  default     = null
}

variable "private_key_path" {
  description = "Filesystem path to the API signing key (CLI deployments only)"
  type        = string
  default     = null
}

variable "fingerprint" {
  description = "Fingerprint for the API signing key (CLI deployments only)"
  type        = string
  default     = null
}

variable "private_key_password" {
  description = "Optional passphrase for the API signing key"
  type        = string
  default     = null
}

variable "region" {
  description = "OCI region in which to deploy"
  type        = string
}

variable "compartment_ocid" {
  type = string
}

variable "enable_oke_iam_policies" {
  description = "Create baseline IAM policies required for OKE cluster/node pool and OCI VCN-native pod networking"
  type        = bool
  default     = true
}

variable "oke_policy_name" {
  description = "Name for the IAM policy that grants OKE permissions"
  type        = string
  default     = "oke-iam-policy"
}

variable "label" {
  description = "A prefix to resources created by the script"
  type        = string
}

variable "k8s_version" {
  type    = string
  default = "v1.34.2"
}

variable "enable_external_kubectl_access" {
  description = "Enable external kubectl access to the OKE API endpoint"
  type        = bool
  default     = false
}

variable "external_kubectl_access_cidr" {
  description = "CIDR block allowed to access the OKE API endpoint when external kubectl access is enabled"
  type        = string
  default     = null

  validation {
    condition = (
      var.external_kubectl_access_cidr == null ||
      try(trimspace(var.external_kubectl_access_cidr), "") == "" ||
      (
        can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/([0-9]|[1-2][0-9]|3[0-2])$", try(trimspace(var.external_kubectl_access_cidr), ""))) &&
        can(cidrhost(try(trimspace(var.external_kubectl_access_cidr), ""), 0))
      )
    )
    error_message = "external_kubectl_access_cidr must be empty/null or a valid CIDR (for example, 203.0.113.0/24)."
  }
}

variable "lb_ingress_source_cidr" {
  description = "CIDR block allowed to reach Kubernetes service load balancers"
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition = (
      can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/([0-9]|[1-2][0-9]|3[0-2])$", try(trimspace(var.lb_ingress_source_cidr), ""))) &&
      can(cidrhost(try(trimspace(var.lb_ingress_source_cidr), ""), 0))
    )
    error_message = "lb_ingress_source_cidr must be a valid CIDR (for example, 0.0.0.0/0 or 203.0.113.0/24)."
  }
}

variable "enable_lb_http_ingress" {
  description = "Allow inbound HTTP (port 80) to load balancers in addition to HTTPS"
  type        = bool
  default     = false
}

variable "node_shape" {
  type    = string
  default = "VM.Standard.A1.Flex"
}
variable "use_latest_platform_oke_image" {
  type    = bool
  default = true
}
variable "node_ocpus" {
  type    = number
  default = 1
}
variable "node_memory" {
  type    = number
  default = 8
}
variable "node_image_ocid" {
  type    = string
  default = null
}

variable "worker_ssh_public_key" {
  type    = string
  default = null
}

variable "nodepool_size" {
  type    = number
  default = 1
}