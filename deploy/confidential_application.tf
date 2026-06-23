data "oci_identity_domain" "selected" {
  provider = oci.home

  domain_id = var.identity_domain_id
}

resource "oci_identity_domains_app" "management_portal_confidential" {
  provider = oci.home

  based_on_template {
    value         = "CustomWebAppTemplateId"
    well_known_id = "CustomWebAppTemplateId"
  }

  display_name  = local.confidential_application_display_name
  idcs_endpoint = data.oci_identity_domain.selected.url
  schemas       = ["urn:ietf:params:scim:schemas:oracle:idcs:App"]

  active                  = true
  all_url_schemes_allowed = true
  allowed_grants          = local.confidential_application_allowed_grants
  allowed_operations      = local.confidential_application_allowed_operations
  bypass_consent          = true
  client_type             = "confidential"
  description             = var.confidential_application_description
  force_delete            = true
  home_page_url           = local.confidential_application_base_url
  is_oauth_client         = true
  landing_page_url        = local.confidential_application_base_url
  login_mechanism         = "OIDC"
  logout_uri              = "${local.confidential_application_base_url}/logout"
  name                    = local.confidential_application_name

  post_logout_redirect_uris = local.confidential_application_post_logout_redirect_uris
  redirect_uris             = local.confidential_application_redirect_uris

  lifecycle {
    ignore_changes = [schemas]

    precondition {
      condition     = length(local.confidential_application_allowed_grants) > 0
      error_message = "At least one confidential application OAuth grant must be enabled."
    }
  }
}
