# OCI Management Portal Local Deployment Guide

This guide explains how to deploy and run the OCI Management Portal outside the OKE and Helm path. It is intended for local development, manual validation, and single-host deployments such as an Oracle Linux compute instance running Gunicorn under `systemd`.

Use this guide when you want to:

- run the application from a cloned repository,
- validate configuration before container or Helm deployment,
- perform a manual Oracle Linux deployment,
- configure or verify the OCI Identity Domain confidential application used for login,
- troubleshoot authentication, firewall, Gunicorn, or environment issues.

For Kubernetes and OCI Resource Manager deployment, use [README_DEPLOYMENT_GUIDE.md](README_DEPLOYMENT_GUIDE.md).

Unless a step explicitly says `cd src`, commands are shown from the repository root.

## Table of Contents

1. [Deployment Modes](#deployment-modes)
2. [Application Runtime Summary](#application-runtime-summary)
3. [Prerequisites](#prerequisites)
4. [OCI and Identity Setup](#oci-and-identity-setup)
5. [Configuration Variables](#configuration-variables)
6. [Developer Workstation Deployment](#developer-workstation-deployment)
7. [Oracle Linux Manual Deployment](#oracle-linux-manual-deployment)
8. [Gunicorn and systemd Service](#gunicorn-and-systemd-service)
9. [Runtime Validation](#runtime-validation)
10. [Operations](#operations)
11. [Troubleshooting](#troubleshooting)
12. [Manual Deployment Notes and Corrections](#manual-deployment-notes-and-corrections)

## Deployment Modes

The application can be run locally in two common ways.

| Mode | Best for | Auth mode | Process manager |
|---|---|---|---|
| Developer workstation | Development, quick validation, debugging | `profile` | Flask CLI or Gunicorn |
| Oracle Linux compute instance | Durable single-host/manual deployment | `instance_principal` | Gunicorn managed by `systemd` |

For short-lived development, Flask is acceptable. For anything that should survive SSH disconnects, terminal closure, reboot, or operator handoff, use Gunicorn with `systemd`.

## Application Runtime Summary

The OCI Management Portal is a Python 3.11 Flask application served by Gunicorn for production-like use.

Important runtime behavior:

- The application entrypoint is `wsgi:app`.
- The source directory is `src/`.
- Python dependencies are pinned in `src/requirements.txt`.
- The default port is `5000`.
- The default session backend is local filesystem cache under `src/session`.
- The application reads configuration from environment variables prefixed with `OCI_MGMT_DASH_`.
- The application supports `profile`, `instance_principal`, `delegation_token`, `workload_principal`, `resource_principal`, and user token exchange flows.

Important routes:

| Route | Purpose |
|---|---|
| `/` | Main portal page |
| `/login` | Start OCI Identity Domain login |
| `/callback` | OIDC callback endpoint |
| `/health` | Basic health check |
| `/ready` | Readiness check after cost cache initialization |
| `/p` | Paginated resource search endpoint |
| `/delete` | Delete/move action endpoint |
| `/extend` | Expiry extension endpoint |
| `/export.csv` | CSV export endpoint |

## Prerequisites

### Common prerequisites

- Python `3.11+`
- Git
- Network access to OCI APIs
- Access to an OCI tenancy and compartment structure used by the portal
- OCI Identity Domain OIDC confidential application
- A cleanup compartment OCID for resources marked for deletion
- A defined tagging model for owner and expiry metadata

### Developer workstation prerequisites

- OCI CLI configuration at `~/.oci/config`, or an alternate config path
- OCI API key and profile with permission to search and act on the target resources
- Redirect URI registered in the OIDC confidential app:

```text
http://localhost:5000/callback
```

### Oracle Linux compute prerequisites

The manual single-host deployment path assumes:

- Oracle Linux 8.x or compatible Oracle Linux host
- Public IP or reachable private network path
- Route table path to required OCI APIs and user browser access path
- Security List or NSG allowing inbound TCP `5000` if exposing the app directly
- Host firewall allowing TCP `5000`
- Instance principal configured through a dynamic group
- IAM policies allowing the portal to read and search resources, read cost data, and perform supported lifecycle actions

For production-facing deployments, place Nginx or a load balancer with TLS in front of Gunicorn rather than exposing Gunicorn directly.

## OCI and Identity Setup

Before running the portal, prepare OCI identity and access.

### 1. Configure tags and cleanup compartment

Confirm these values before deployment:

| Item | Example | Why it matters |
|---|---|---|
| Managed tag namespace | `Usage-Management` | Used to identify managed resources |
| Owner or creator tag key | `Owner` | Used to match resources to signed-in users |
| Expiry filter namespace | `Usage-Management` | Namespace for expiry filtering |
| Expiry filter key | `Expires` | Used by the search query to find expired resources |
| Cleanup compartment OCID | `ocid1.compartment...` | Target compartment for delete and move workflow |

### 2. Configure OCI Identity Domain confidential application

Create or reuse an OCI Identity Domain confidential application for OIDC login. This is the application the portal redirects users to during `/login`, and it must be configured before local login can succeed.

Recommended configuration checklist:

1. Open your OCI Identity Domain.
2. Create a new application or open the existing portal application.
3. Choose an application type that supports OIDC with a client secret.
4. Enable Authorization Code login flow.
5. Register the exact redirect URI for the environment you are deploying.
6. Assign users or groups who are allowed to sign in.
7. Save the application and copy the client ID and client secret for the portal configuration.

If you are creating the application manually in the OCI Console, align it to the same model used by the Terraform implementation in [deploy/confidential_application.tf](deploy/confidential_application.tf).

Recommended manual configuration values:

| Setting | Recommended value |
|---|---|
| Template or app type | Custom web application or equivalent OIDC web app |
| Client type | `confidential` |
| Login mechanism | `OIDC` |
| OAuth client enabled | enabled |
| Allowed grants | `authorization_code`, `client_credentials` |
| Allowed operations | `introspect` |
| User consent | bypass or disabled where your policy allows it |
| Home page URL | portal base URL, for example `http://localhost:5000` |
| Landing page URL | portal base URL, for example `http://localhost:5000` |
| Logout URL | portal base URL + `/logout` |
| Redirect URI | portal base URL + `/callback` |
| Post logout redirect URI | portal base URL |

For a local workstation example, the values look like this:

| Setting | Example |
|---|---|
| Home page URL | `http://localhost:5000` |
| Landing page URL | `http://localhost:5000` |
| Logout URL | `http://localhost:5000/logout` |
| Redirect URI | `http://localhost:5000/callback` |
| Post logout redirect URI | `http://localhost:5000` |

Required application settings:

- Confidential client or equivalent client-secret-based OIDC application
- Authorization code flow enabled
- Client credentials flow enabled
- Introspection operation enabled
- Client ID available to the portal
- Client secret available to the portal
- Redirect URI matching the deployed portal URL plus `/callback`
- Post logout redirect URI matching the portal base URL, if used

Recommended values to capture from the application:

| Value | Used by |
|---|---|
| Identity Domain endpoint | `OCI_MGMT_DASH_IDM_ENDPOINT` |
| Client ID | `OCI_MGMT_DASH_CLIENT_ID` |
| Client secret | `OCI_MGMT_DASH_CLIENT_SECRET` |
| Redirect URI | Must match `OCI_MGMT_DASH_APP_URI` + `/callback` |

Redirect URI examples:

```text
Local workstation callback:
http://localhost:5000/callback

Compute instance callback:
http://<public-ip>:5000/callback

HTTPS fronted callback:
https://<portal-domain>/callback
```

Post logout redirect examples:

```text
Local workstation:
http://localhost:5000

Compute instance:
http://<public-ip>:5000

HTTPS fronted deployment:
https://<portal-domain>
```

Operational checks before continuing:

- The redirect URI in the confidential application exactly matches the portal callback URL.
- The signed-in users are assigned to the application or to an allowed group.
- The copied client ID and client secret are current and not expired or rotated without updating the portal.
- The application URL used in the portal configuration matches the host users will actually open in their browser.

If the callback URL does not exactly match the Identity Domain application configuration, login can fail even when the application and host are deployed correctly.

### 3. Configure OCI authorization

For developer workstation runs, the application normally uses `profile` authentication from `~/.oci/config`.

For Oracle Linux compute deployments, use `instance_principal`:

1. Create a dynamic group that matches the compute instance or its compartment.
2. Add IAM policies for the actions the portal must perform.
3. Start the application with `OCI_MGMT_DASH_AUTH_TYPE=instance_principal`.

Initial broad validation policies are often used during early testing, but production deployments should be narrowed to the minimum resource families and compartments required.

Useful policy categories:

```text
Allow dynamic-group <dynamic-group-name> to inspect compartments in tenancy
Allow dynamic-group <dynamic-group-name> to read usage-reports in tenancy
Allow dynamic-group <dynamic-group-name> to read all-resources in tenancy
```

For delete and extend operations, grant the dynamic group the specific manage or use permissions required for the supported resource types and target compartments. If a broad policy is used temporarily for validation, reduce it before production handoff.

## Configuration Variables

The application reads environment variables with the `OCI_MGMT_DASH_` prefix.

> Important: Older manual notes may reference `OCIDOMAIN_*` variables. This codebase uses `OCI_MGMT_DASH_*`. Use the variables below for this repository.

### Required variables

| Variable | Example | Description |
|---|---|---|
| `OCI_MGMT_DASH_TAG_NAMESPACE` | `Usage-Management` | Namespace used to identify managed resources |
| `OCI_MGMT_DASH_TAG_KEY` | `Owner` | Owner or creator tag key |
| `OCI_MGMT_DASH_FILTER_KEY` | `Expires` | Expiry filter tag key |
| `OCI_MGMT_DASH_CLEANUP_CMP` | `ocid1.compartment...` | Cleanup compartment OCID |
| `OCI_MGMT_DASH_IDM_ENDPOINT` | `https://idcs-xxxx.identity.oraclecloud.com:443` | OCI Identity Domain endpoint |
| `OCI_MGMT_DASH_CLIENT_ID` | `<client-id>` | OIDC confidential app client ID |
| `OCI_MGMT_DASH_CLIENT_SECRET` | `<client-secret>` | OIDC confidential app client secret |
| `OCI_MGMT_DASH_FILTER_NAMESPACE` | `Usage-Management` | Namespace used with the expiry filter key |
| `OCI_MGMT_DASH_APP_URI` | `http://localhost:5000` | Public application base URL |
| `OCI_MGMT_DASH_PROXY` | `false` | Set `true` when behind a trusted reverse proxy |
| `OCI_MGMT_DASH_AUTH_TYPE` | `profile` | OCI auth mode |
| `OCI_MGMT_DASH_LOG_LEVEL` | `info` | Application log level |

### Common optional variables

| Variable | Default | Description |
|---|---|---|
| `OCI_MGMT_DASH_CONFIG_FILE` | `~/.oci/config` | OCI config file for profile auth |
| `OCI_MGMT_DASH_PROFILE` | `DEFAULT` | OCI profile name |
| `OCI_MGMT_DASH_SESSION_BACKEND` | `filesystem` | `filesystem`, `redis`, or `valkey` |
| `OCI_MGMT_DASH_SESSION_REDIS_URL` | unset | Required for Redis or Valkey sessions |
| `OCI_MGMT_DASH_USER_SCOPED_OCI_CALLS` | `false` | Use per-user token exchange for Search/Delete/Extend |


### Local shell environment example

For shell-based runs, create a local environment file from `sample.env`:

```bash
cp sample.env local.env
vi local.env
```

Example for a developer workstation:

```bash
export OCI_MGMT_DASH_TAG_NAMESPACE="Usage-Management"
export OCI_MGMT_DASH_TAG_KEY="Owner"
export OCI_MGMT_DASH_FILTER_NAMESPACE="Usage-Management"
export OCI_MGMT_DASH_FILTER_KEY="Expires"
export OCI_MGMT_DASH_CLEANUP_CMP="ocid1.compartment.oc1..replace_me"

export OCI_MGMT_DASH_IDM_ENDPOINT="https://idcs-replace.identity.oraclecloud.com:443"
export OCI_MGMT_DASH_CLIENT_ID="replace-client-id"
export OCI_MGMT_DASH_CLIENT_SECRET="replace-client-secret"
export OCI_MGMT_DASH_APP_URI="http://localhost:5000"

export OCI_MGMT_DASH_AUTH_TYPE="profile"
export OCI_MGMT_DASH_CONFIG_FILE="$HOME/.oci/config"
export OCI_MGMT_DASH_PROFILE="DEFAULT"
export OCI_MGMT_DASH_SESSION_BACKEND="filesystem"
```

Load it before starting the app:

```bash
source local.env
```

### Create Environment File for systemd

For `systemd`, use plain `KEY=value` lines without `export`.

File:

```text
/etc/sysconfig/oci-management-portal
```

Example:

```ini
OCI_MGMT_DASH_TAG_NAMESPACE=Usage-Management
OCI_MGMT_DASH_TAG_KEY=Owner
OCI_MGMT_DASH_FILTER_NAMESPACE=Usage-Management
OCI_MGMT_DASH_FILTER_KEY=Expires
OCI_MGMT_DASH_CLEANUP_CMP=ocid1.compartment.oc1..replace_me

OCI_MGMT_DASH_IDM_ENDPOINT=https://idcs-replace.identity.oraclecloud.com:443
OCI_MGMT_DASH_CLIENT_ID=replace-client-id
OCI_MGMT_DASH_CLIENT_SECRET=replace-client-secret
OCI_MGMT_DASH_APP_URI=http://<public-ip>:5000

OCI_MGMT_DASH_AUTH_TYPE=instance_principal
OCI_MGMT_DASH_SESSION_BACKEND=filesystem
OCI_MGMT_DASH_LOG_LEVEL=info
```

Protect the file because it contains secrets:

```bash
sudo chown root:gunicorn /etc/sysconfig/oci-management-portal
sudo chmod 640 /etc/sysconfig/oci-management-portal
```

This file is consumed by the `EnvironmentFile` directive in the `gunicorn.service` unit later in this guide.

## Developer Workstation Deployment

Use this path for local development and validation.

### 1. Clone or enter the repository

```bash
cd /path/to/oci-management-portal
```

The repository root should contain:

```text
Dockerfile
sample.env
src/
```

### 2. Create a Python virtual environment

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/requirements.txt
```

Validate the installation:

```bash
python --version
python -m pip check
```

### 3. Prepare local configuration

```bash
cp sample.env local.env
vi local.env
source local.env
```

Minimum local configuration:

- set OIDC values,
- set tag and filter values,
- set cleanup compartment,
- set `OCI_MGMT_DASH_AUTH_TYPE=profile`,
- set `OCI_MGMT_DASH_APP_URI=http://localhost:5000`,
- confirm the Identity Domain redirect URI includes `http://localhost:5000/callback`.

### 4. Start with Flask for development

```bash
cd src
flask --app wsgi:app run --debug --host 0.0.0.0 --port 5000
```

Open:

```text
http://localhost:5000
```

Use Flask only for development. It is not durable and should not be used for a long-running manual deployment.

### 5. Start with Gunicorn for production-like local testing

From `src/`:

```bash
gunicorn -c gunicorn.config.py wsgi:app
```

By default, Gunicorn binds to:

```text
0.0.0.0:5000
```

Override Gunicorn settings if needed:

```bash
export GUNICORN_BIND="127.0.0.1:5000"
export GUNICORN_WORKERS="1"
export GUNICORN_THREADS="4"
gunicorn -c gunicorn.config.py wsgi:app
```

## Oracle Linux Manual Deployment

Use this path for a durable manual deployment on a single Oracle Linux compute instance.

The steps below assume:

- runtime user: `gunicorn`
- application root: `/home/gunicorn/oci-management-portal`
- source directory: `/home/gunicorn/oci-management-portal/src`
- virtual environment: `/home/gunicorn/venv/flaskapp`
- service name: `gunicorn`

Adjust paths if your clone directory is different.

### 1. Prepare compute networking

Confirm the compute instance has:

- public IP or reachable private path,
- route table allowing required outbound access,
- OCI Security List or NSG allowing inbound TCP `5000` from approved sources,
- host firewall opened for TCP `5000`.

For public access, avoid leaving `0.0.0.0/0` open longer than necessary. Restrict source CIDRs where possible.

### 2. Create dedicated runtime user

```bash
sudo useradd -m gunicorn
sudo passwd -l gunicorn
```

Verify:

```bash
id gunicorn
ls -ld /home/gunicorn
```

### 3. Install system packages

```bash
sudo dnf install -y python3.11 python3.11-devel git firewalld
```

Confirm:

```bash
python3.11 --version
git --version
```

### 4. Create Python virtual environment

```bash
sudo -u gunicorn -H bash
cd /home/gunicorn
mkdir -p venv
python3.11 -m venv venv/flaskapp
source /home/gunicorn/venv/flaskapp/bin/activate
python -m pip install --upgrade pip
exit
```

### 5. Clone the application repository

```bash
sudo -u gunicorn -H bash
cd /home/gunicorn
git clone https://github.com/flynnkc/oci-management-portal.git
exit
```

Expected application source location:

```text
/home/gunicorn/oci-management-portal/src
```

If your repository name or location differs, update the service file paths accordingly.

### 6. Install Python dependencies

```bash
sudo -u gunicorn -H bash
cd /home/gunicorn/oci-management-portal
source /home/gunicorn/venv/flaskapp/bin/activate
python -m pip install -r src/requirements.txt
python -m pip check
exit
```

`PyJWT`, `requests`, `oci`, and `gunicorn` are already included in `src/requirements.txt`; do not install duplicate packages manually unless troubleshooting a failed environment.

### 7. Open host firewall port

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

Expected output includes:

```text
5000/tcp
```

Remember that both OCI network rules and the OS firewall must allow traffic. Opening only the OCI Security List or NSG is not enough if `firewalld` blocks the port.

### 8. Create Environment File for systemd

```bash
sudo vi /etc/sysconfig/oci-management-portal
```

Use the [Create Environment File for systemd](#create-environment-file-for-systemd) example from the configuration section. Then protect the file:

```bash
sudo chown root:gunicorn /etc/sysconfig/oci-management-portal
sudo chmod 640 /etc/sysconfig/oci-management-portal
sudo ls -l /etc/sysconfig/oci-management-portal
```

## Gunicorn and systemd Service

Create the service file:

```bash
sudo vi /etc/systemd/system/gunicorn.service
```

Recommended service definition:

```ini
[Unit]
Description=OCI Management Portal Gunicorn Service
After=network.target

[Service]
User=gunicorn
Group=gunicorn
WorkingDirectory=/home/gunicorn/oci-management-portal/src
EnvironmentFile=-/etc/sysconfig/oci-management-portal
ExecStart=/bin/bash -lc '/home/gunicorn/venv/flaskapp/bin/gunicorn -c gunicorn.config.py wsgi:app'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Important notes:

- `WorkingDirectory` must be the `src/` directory.
- The Gunicorn executable path must match the virtual environment path you created.
- The environment file path must match the file created earlier.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn
sudo systemctl status gunicorn
```

Tail logs:

```bash
sudo journalctl -u gunicorn -f
```

## Runtime Validation

### Basic endpoint checks

From the local host:

```bash
curl -i http://127.0.0.1:5000/health
curl -i http://127.0.0.1:5000/ready
```

Expected:

- `/health` returns `200` and `healthy`
- `/ready` returns `200` and `ready`

If binding to all interfaces, you can also test with the public IP:

```bash
curl -i http://<public-ip>:5000/health
```

### Browser validation

Confirm:

- the portal home page loads,
- `/login` redirects to the OCI Identity Domain login page,
- login returns to `/callback`,
- the signed-in user reaches the portal successfully,
- expired resources are visible when expected,
- extend and delete actions are available only where expected.

### Confidential app validation checklist

If login does not complete, re-check:

- `OCI_MGMT_DASH_APP_URI`
- registered redirect URI in the confidential application
- client ID and client secret
- Identity Domain endpoint
- user or group assignment to the confidential application
- browser URL exactly matching the configured callback host

## Operations

### Restart Gunicorn

```bash
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
```

### Reload after configuration change

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

### View logs

```bash
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u gunicorn -f
```

### Stop the service

```bash
sudo systemctl stop gunicorn
```

## Troubleshooting

### Login redirects incorrectly or callback fails

Check:

- `OCI_MGMT_DASH_APP_URI`
- `OCI_MGMT_DASH_IDM_ENDPOINT`
- `OCI_MGMT_DASH_CLIENT_ID`
- `OCI_MGMT_DASH_CLIENT_SECRET`
- exact redirect URI in the confidential application
- user assignment to the confidential application

If the portal is opened at `http://<host>:5000`, the redirect URI in the confidential app must also use `http://<host>:5000/callback`. A mismatch between `localhost`, public IP, DNS host, or HTTPS and HTTP is enough to break login.

### App starts but page is unreachable

Check:

- Gunicorn bind address
- OCI Security List or NSG rules
- `firewalld` rules
- whether the service is listening on port `5000`

Useful commands:

```bash
sudo ss -ltnp | grep 5000
sudo firewall-cmd --list-ports
sudo journalctl -u gunicorn -n 100 --no-pager
```

### Health works but ready fails

Check:

- OCI auth mode
- IAM policies for cost and search access
- startup logs for OCI API failures

### Search returns no resources

Check:

- tag namespace and key values
- filter namespace and key values
- cleanup compartment value
- owner or creator tags on target resources
- region and tenancy scope

### Service fails under systemd

Check:

- virtual environment path
- `WorkingDirectory`
- environment file permissions
- missing Python dependencies

Useful commands:

```bash
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -xe --no-pager
```

## Manual Deployment Notes and Corrections

This guide aligns the original manual deployment process with the current repository structure and configuration model.

Important corrections applied in this version:

- use `OCI_MGMT_DASH_*` variables instead of older `OCIDOMAIN_*` naming,
- use `src/requirements.txt` rather than ad hoc package installation,
- use `wsgi:app` from the `src/` working directory,
- use `gunicorn.config.py` instead of a hard-coded bare Gunicorn command where possible,
- include both OCI-side and host-side firewall checks,
- include explicit confidential app and callback validation steps.
