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

variable "label" {
  description = "A prefix to resources created by the script"
  type = string
}

variable "k8s_version" {
  type    = string
  default = "v1.34.2"
}
variable "node_shape" {
  type    = string
  default = "VM.Standard.E4.Flex"
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
  type = string
  default = null
}

variable "nodepool_size" {
  type = number
  default = 1
}