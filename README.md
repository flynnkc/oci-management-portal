# OCI Management Dashboard

## Installation

### 1. Creat Identity Domain Confidential Application

1. Integrated Applications and _Add application_. Select _Confidential Application_.
    - Give a name and _Next_
    - Resource server _Primary Audience_
    - _Configure this application as a client now_
    - _Client Credentials_ and _Authorization Code_ grants
    - _Redirect URL_ as callback URL
    - Client type _Confidential_
    - Client IP address
    - Token issuance policy
    - Next and Activate

## Configuration

The application uses environment variables to get configurations:

- OCIDOMAIN_AUTH_TYPE

    Authentication type for application to use for connecting to OCI:

  - profile
  - instance_principal
  - delegation_token
  - workload_principal

- OCIDOMAIN_IDM_ENDPOINT

    The OIDC provider endpoint _(ex. `https://idcs-xyz.identity.oraclecloud.com`)_

- OCIDOMAIN_CLIENT_ID

    The OIDC provider client ID _(ex. `12345`)_

- OCIDOMAIN_CLIENT_SECRET

    The OIDC provider secret _(ex. `abcdef`)_

- OCIDOMAIN_APP_URI

    URI to reach application _(ex. `https://foo.bar:4431`)_

- OCIDOMAIN_TAG_NAMESPACE

    Tag namespace for Search _(ex. `Team-A`)_

- OCIDOMAIN_TAG_KEY

    Tag key for Search _(ex. `User`)_

- OCIDOMAIN_FILTER_NAMESPACE

    Tag namespace for Filter _(ex. `Admin`)_

- OCIDOMAIN_FILTER_KEY

    Tag key for Filter _(ex. `Expires`)_

- OCIDOMAIN_PROFILE

    If using Profile authentication, profile to use in Search and Delete _(Default: DEFAULT)_

- OCIDOMAIN_LOCATION

    If using Profile authentication, OCI config file location _(Default: ~/.oci/config)_
