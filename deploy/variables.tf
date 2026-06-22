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

variable "create_endpoint_subnet" {
  description = "Create a dedicated private subnet for the OKE API endpoint"
  type        = bool
  default     = true
}

variable "enable_oke_iam_policies" {
  description = "Create baseline IAM policies required for OKE cluster and node pool operation"
  type        = bool
  default     = true
}

variable "oke_policy_name" {
  description = "Name for the IAM policy that grants OKE permissions"
  type        = string
  default     = "oke-iam-policy"
}

variable "identity_domain_id" {
  description = "OCID of the existing OCI Identity Domain where the confidential application will be created"
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.domain\\.", trimspace(var.identity_domain_id)))
    error_message = "identity_domain_id must be an OCI Identity Domain OCID."
  }
}

variable "confidential_application_name" {
  description = "Immutable OAuth client name/client ID for the confidential application. Leave null to derive it from label."
  type        = string
  default     = null

  validation {
    condition = (
      var.confidential_application_name == null ||
      can(regex("^[A-Za-z0-9._-]+$", trimspace(var.confidential_application_name)))
    )
    error_message = "confidential_application_name can contain only letters, numbers, dots, underscores, and hyphens."
  }
}

variable "confidential_application_display_name" {
  description = "Display name for the OCI Identity Domain confidential application. Leave null to derive it from label."
  type        = string
  default     = null
}

variable "confidential_application_description" {
  description = "Description for the OCI Identity Domain confidential application"
  type        = string
  default     = "Confidential OIDC application for OCI Management Portal"
}

variable "confidential_application_base_url" {
  description = "Public base URL for the management portal; used to derive default callback and post-logout redirect URIs"
  type        = string
  default     = "http://localhost:5000"

  validation {
    condition     = can(regex("^https?://", trimspace(var.confidential_application_base_url)))
    error_message = "confidential_application_base_url must start with http:// or https://."
  }
}

variable "confidential_application_redirect_uris" {
  description = "Redirect URIs for the confidential application. Leave empty to use confidential_application_base_url + /callback."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for uri in var.confidential_application_redirect_uris :
      can(regex("^https?://", trimspace(uri)))
    ])
    error_message = "Each confidential_application_redirect_uris entry must start with http:// or https://."
  }
}

variable "confidential_application_post_logout_redirect_uris" {
  description = "Post-logout redirect URIs for the confidential application. Leave empty to use confidential_application_base_url."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for uri in var.confidential_application_post_logout_redirect_uris :
      can(regex("^https?://", trimspace(uri)))
    ])
    error_message = "Each confidential_application_post_logout_redirect_uris entry must start with http:// or https://."
  }
}

variable "confidential_application_authorization_code_grant_enabled" {
  description = "Enable the OAuth authorization_code grant for portal user login"
  type        = bool
  default     = true
}

variable "confidential_application_client_credentials_grant_enabled" {
  description = "Enable the OAuth client_credentials grant for service-to-service access"
  type        = bool
  default     = true
}

variable "confidential_application_refresh_token_grant_enabled" {
  description = "Enable the OAuth refresh_token grant"
  type        = bool
  default     = false
}

variable "confidential_application_implicit_grant_enabled" {
  description = "Enable the OAuth implicit grant"
  type        = bool
  default     = false
}

variable "confidential_application_password_grant_enabled" {
  description = "Enable the OAuth password grant"
  type        = bool
  default     = false
}

variable "confidential_application_jwt_bearer_grant_enabled" {
  description = "Enable the OAuth JWT bearer grant"
  type        = bool
  default     = false
}

variable "confidential_application_allowed_grant" {
  description = "Legacy single OAuth grant value. Prefer the grant boolean variables or confidential_application_allowed_grants."
  type        = string
  default     = null

  validation {
    condition = (
      var.confidential_application_allowed_grant == null ||
      try(trimspace(var.confidential_application_allowed_grant), "") == "" ||
      contains([
        "authorization_code",
        "client_credentials",
        "refresh_token",
        "implicit",
        "password",
        "urn:ietf:params:oauth:grant-type:jwt-bearer"
      ], try(trimspace(var.confidential_application_allowed_grant), ""))
    )
    error_message = "confidential_application_allowed_grant must be one of: authorization_code, client_credentials, refresh_token, implicit, password, urn:ietf:params:oauth:grant-type:jwt-bearer."
  }
}

variable "confidential_application_allowed_grants" {
  description = "Additional OAuth grant types enabled for the confidential application"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for grant in var.confidential_application_allowed_grants :
      contains([
        "authorization_code",
        "client_credentials",
        "refresh_token",
        "implicit",
        "password",
        "urn:ietf:params:oauth:grant-type:jwt-bearer"
      ], grant)
    ])
    error_message = "confidential_application_allowed_grants entries must be one of: authorization_code, client_credentials, refresh_token, implicit, password, urn:ietf:params:oauth:grant-type:jwt-bearer."
  }
}

variable "confidential_application_allowed_operations" {
  description = "Additional OAuth client operations enabled for the confidential application"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for operation in var.confidential_application_allowed_operations :
      contains(["introspect", "onBehalfOfUser"], operation)
    ])
    error_message = "confidential_application_allowed_operations entries must be introspect or onBehalfOfUser."
  }
}

variable "confidential_application_allowed_operation" {
  description = "Primary OAuth client operation enabled for the confidential application"
  type        = string
  default     = "introspect"

  validation {
    condition     = contains(["introspect", "onBehalfOfUser"], try(trimspace(var.confidential_application_allowed_operation), ""))
    error_message = "confidential_application_allowed_operation must be introspect or onBehalfOfUser."
  }
}

variable "confidential_application_all_url_schemes_allowed" {
  description = "Allow non-HTTPS callback URLs such as localhost or a plain HTTP load balancer URL"
  type        = bool
  default     = true
}

variable "confidential_application_bypass_consent" {
  description = "Skip user consent for the confidential application's configured scopes"
  type        = bool
  default     = true
}

variable "confidential_application_force_delete" {
  description = "Force delete the confidential application during terraform destroy"
  type        = bool
  default     = true
}

variable "label" {
  description = "A prefix to resources created by the script"
  type        = string
}

variable "k8s_version" {
  description = "OKE Kubernetes version. Leave null to use the latest OCI-supported patch version in the selected region."
  type        = string
  default     = null

  validation {
    condition = (
      var.k8s_version == null ||
      try(trimspace(var.k8s_version), "") == "" ||
      can(regex("^v?[0-9]+\\.[0-9]+\\.[0-9]+$", trimspace(var.k8s_version)))
    )
    error_message = "k8s_version must be null/empty or a full Kubernetes patch version, for example v1.34.2."
  }
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
