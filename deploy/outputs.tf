output "identity_domain_endpoint" {
  description = "OIDC endpoint for the selected OCI Identity Domain"
  value       = data.oci_identity_domain.selected.url
}

output "confidential_application_id" {
  description = "Identity Domain SCIM ID of the management portal confidential application"
  value       = oci_identity_domains_app.management_portal_confidential.id
}

output "confidential_application_ocid" {
  description = "OCI OCID of the management portal confidential application"
  value       = oci_identity_domains_app.management_portal_confidential.ocid
}

output "confidential_application_client_id" {
  description = "OAuth client ID to use as OCI_MGMT_DASH_CLIENT_ID"
  value       = oci_identity_domains_app.management_portal_confidential.name
}

output "confidential_application_client_secret" {
  description = "OAuth client secret to use as OCI_MGMT_DASH_CLIENT_SECRET"
  value       = oci_identity_domains_app.management_portal_confidential.client_secret
  sensitive   = true
}
