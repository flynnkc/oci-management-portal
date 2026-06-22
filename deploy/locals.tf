locals {
  endpoint_subnet_id = (
    var.create_endpoint_subnet
    ? oci_core_subnet.subnet_endpoint_private[0].id
    : oci_core_subnet.subnet_nodes_private.id
  )

  region_map  = { for region in data.oci_identity_regions.all.regions : region.key => region.name }
  home_region = lookup(local.region_map, data.oci_identity_tenancy.tenancy.home_region_key)

  # Infer node architecture from shape family for OKE node source filtering.
  node_pool_os_arch = can(regex("^VM\\.Standard\\.A", var.node_shape)) ? "aarch64" : "amd64"

  selected_node_image_id = var.use_latest_platform_oke_image ? local.latest_platform_oke_image_id : var.node_image_ocid
}

locals {
  confidential_application_base_url = trimsuffix(trimspace(var.confidential_application_base_url), "/")
  confidential_application_label_id = trim(replace(lower(var.label), "/[^a-z0-9._-]/", "-"), "-")
  confidential_application_name_prefix = (
    local.confidential_application_label_id != ""
    ? local.confidential_application_label_id
    : "oci-management-portal"
  )

  confidential_application_name = (
    try(trimspace(var.confidential_application_name), "") != ""
    ? trimspace(var.confidential_application_name)
    : "${local.confidential_application_name_prefix}-management-portal"
  )

  confidential_application_display_name = (
    try(trimspace(var.confidential_application_display_name), "") != ""
    ? trimspace(var.confidential_application_display_name)
    : "${var.label} Management Portal"
  )

  confidential_application_redirect_uris = (
    length(var.confidential_application_redirect_uris) > 0
    ? [for uri in var.confidential_application_redirect_uris : trimsuffix(trimspace(uri), "/")]
    : ["${local.confidential_application_base_url}/callback"]
  )

  confidential_application_post_logout_redirect_uris = (
    length(var.confidential_application_post_logout_redirect_uris) > 0
    ? [for uri in var.confidential_application_post_logout_redirect_uris : trimsuffix(trimspace(uri), "/")]
    : [local.confidential_application_base_url]
  )

  confidential_application_allowed_grants = distinct(compact(concat(
    [
      var.confidential_application_authorization_code_grant_enabled ? "authorization_code" : "",
      var.confidential_application_client_credentials_grant_enabled ? "client_credentials" : "",
      var.confidential_application_refresh_token_grant_enabled ? "refresh_token" : "",
      var.confidential_application_implicit_grant_enabled ? "implicit" : "",
      var.confidential_application_password_grant_enabled ? "password" : "",
      var.confidential_application_jwt_bearer_grant_enabled ? "urn:ietf:params:oauth:grant-type:jwt-bearer" : ""
    ],
    [for grant in var.confidential_application_allowed_grants : trimspace(grant)]
  )))

  confidential_application_allowed_operations = distinct(compact(concat(
    [try(trimspace(var.confidential_application_allowed_operation), "")],
    [for operation in var.confidential_application_allowed_operations : trimspace(operation)]
  )))
}

locals {
  supported_k8s_version_sort_keys = [
    for version in data.oci_containerengine_cluster_option.all.kubernetes_versions :
    format(
      "%03d.%03d.%03d:%s",
      tonumber(split(".", trimprefix(version, "v"))[0]),
      tonumber(split(".", trimprefix(version, "v"))[1]),
      tonumber(split(".", trimprefix(version, "v"))[2]),
      version
    )
  ]

  latest_supported_k8s_version = try(
    split(":", sort(local.supported_k8s_version_sort_keys)[length(local.supported_k8s_version_sort_keys) - 1])[1],
    null
  )

  effective_k8s_version = try(trimspace(var.k8s_version), "") != "" ? trimspace(var.k8s_version) : local.latest_supported_k8s_version
}

locals {
  # Pick the first OKE-supported image source for this k8s version/arch.
  latest_platform_oke_image_id = try([
    for s in data.oci_containerengine_node_pool_option.oke.sources : s.image_id
    if s.source_type == "IMAGE"
  ][0], null)
}
