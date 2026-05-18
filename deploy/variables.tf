variable "tenancy_ocid" { type = string }
variable "compartment_ocid" { type = string }

variable "user_ocid" { type = string }
variable "fingerprint" { type = string }
variable "private_key" {
  type      = string
  sensitive = true
}

variable "region" {
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
}