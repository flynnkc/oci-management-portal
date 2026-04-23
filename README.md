# OCI Management Portal

OCI Management Portal is a Flask web application for discovering and managing OCI resources tagged for ownership and lifecycle control. It supports authenticated user views, search/filter flows, resource expiry extension, and managed delete workflows.

Use this README to configure, run locally (Flask or Gunicorn), deploy on Oracle Linux, or build and run the container image.

## Related Project Dependencies

This project depends on two companion projects for lifecycle operations. The portal initiates and tracks lifecycle actions, while these companion tools perform key backend enforcement tasks that keep resource hygiene and expiry policy automation working end-to-end:

1. **Cleanup compartment asset removal**: <https://github.com/therealcmj/ociextirpater>
   - The portal’s delete flow moves eligible resources into a cleanup compartment.
   - `ociextirpater` is the downstream cleanup engine that removes those moved assets, preventing long-lived buildup and completing the deletion lifecycle.
2. **Expiry tag updates via tag defaults**: <https://github.com/flynnkc/tag-updater>
   - The portal’s extend flow relies on standardized expiry tagging behavior.
   - `tag-updater` applies/updates expiry values using tag default workflows so extension behavior remains consistent and policy-driven across resources.

## Configuration

The app reads configuration from environment variables (prefix: `OCI_MGMT_DASH_`).

| Variable | Required | Default | Description |
|---|---|---|---|
| `OCI_MGMT_DASH_TAG_NAMESPACE` | Yes | — | Namespace used to identify managed resources. |
| `OCI_MGMT_DASH_TAG_KEY` | Yes | — | Tag key used to identify managed resources (for example, creator/owner key). |
| `OCI_MGMT_DASH_FILTER_KEY` | Yes | — | Tag key used for filtering/expiry behavior. |
| `OCI_MGMT_DASH_FILTER_NAMESPACE` | No | `OCI_MGMT_DASH_TAG_NAMESPACE` | Namespace used with `FILTER_KEY`. |
| `OCI_MGMT_DASH_CLEANUP_CMP` | Yes | — | Target cleanup compartment OCID for move/delete operations. |
| `OCI_MGMT_DASH_AUTH_TYPE` | No | `profile` | OCI auth mode: `profile`, `instance_principal`, `delegation_token`, `workload_principal`, or `resource_principal`. |
| `OCI_MGMT_DASH_CONFIG_FILE` | No | `~/.oci/config` | OCI config file path (used with `profile` auth). |
| `OCI_MGMT_DASH_PROFILE` | No | `DEFAULT` | OCI profile name (used with `profile` auth). |
| `OCI_MGMT_DASH_IDM_ENDPOINT` | Yes | — | OIDC endpoint for your OCI Identity Domain (for example, `https://idcs-xxxx.identity.oraclecloud.com:443`). |
| `OCI_MGMT_DASH_CLIENT_ID` | Yes | — | OIDC confidential application client ID. |
| `OCI_MGMT_DASH_CLIENT_SECRET` | Yes | — | OIDC confidential application client secret. |
| `OCI_MGMT_DASH_APP_URI` | No | `http://localhost:5000` | Public application base URL used for callback/redirect generation. |
| `OCI_MGMT_DASH_PROXY` | No | `false` | Set `true` when behind a trusted reverse proxy forwarding `X-Forwarded-*` headers. |
| `OCI_MGMT_DASH_SESSION_BACKEND` | No | `filesystem` | Session store backend: `filesystem` (single pod), `redis`, or `valkey` (shared cache for multi-pod). |
| `OCI_MGMT_DASH_SESSION_REDIS_URL` | Conditionally (required for `redis`/`valkey`) | — | Connection URL for Redis-compatible cache (Redis 7.0, Valkey 7.2, or Valkey 8.1). Example: `redis://cache-host:6379/0`. |
| `OCI_MGMT_DASH_SESSION_REDIS_USERNAME` | No | — | Optional Redis ACL username. If provided, overrides username embedded in `SESSION_REDIS_URL`. |
| `OCI_MGMT_DASH_SESSION_REDIS_PASSWORD` | No | — | Optional Redis password (or ACL password). If provided, overrides password embedded in `SESSION_REDIS_URL`. |
| `OCI_MGMT_DASH_SESSION_KEY_PREFIX` | No | `omid:` | Key prefix used for session entries in Redis/Valkey. |
| `OCI_MGMT_DASH_LOG_LEVEL` | No | `info` | Application log level (`debug`, `info`, etc.). |
| `OCI_MGMT_DASH_LOG_FORMAT` | No | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | Python logging format string. |

> Tip: Start from `sample.env`, update values for your tenancy/domain, then source it before running.

### OIDC session handling

During login callback, the app validates the ID token and performs login-time access-token introspection to enrich/confirm user context. It then stores only minimal user session data (`user`, `email`, `domain`, `sub`) and does **not** persist access tokens in the session.

### Multi-pod session cache

For multi-pod deployments, configure a shared Redis-compatible backend so all pods can read/write the same user session state.

Examples:

```bash
# Redis 7.0
export OCI_MGMT_DASH_SESSION_BACKEND="redis"
export OCI_MGMT_DASH_SESSION_REDIS_URL="redis://redis-7-0.default.svc.cluster.local:6379/0"
export OCI_MGMT_DASH_SESSION_REDIS_USERNAME="default"
export OCI_MGMT_DASH_SESSION_REDIS_PASSWORD="<redis-password>"

# Valkey 7.2
export OCI_MGMT_DASH_SESSION_BACKEND="valkey"
export OCI_MGMT_DASH_SESSION_REDIS_URL="redis://valkey-7-2.default.svc.cluster.local:6379/0"
export OCI_MGMT_DASH_SESSION_REDIS_USERNAME="default"
export OCI_MGMT_DASH_SESSION_REDIS_PASSWORD="<valkey-password>"

# Valkey 8.1
export OCI_MGMT_DASH_SESSION_BACKEND="valkey"
export OCI_MGMT_DASH_SESSION_REDIS_URL="redis://valkey-8-1.default.svc.cluster.local:6379/0"
export OCI_MGMT_DASH_SESSION_REDIS_USERNAME="default"
export OCI_MGMT_DASH_SESSION_REDIS_PASSWORD="<valkey-password>"
```

If you keep `OCI_MGMT_DASH_SESSION_BACKEND=filesystem`, sessions are local to each pod and are not suitable for multi-pod session sharing.

## Run Locally

### 1) Prepare Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt
```

### 2) Load configuration

```bash
source sample.env
```

Update `sample.env` with real values before running.

### 3) Run with Flask (development)

```bash
cd src
flask --app wsgi:app run --debug
```

### 4) Run with Gunicorn (production-like local run)

```bash
cd src
gunicorn -c gunicorn.config.py wsgi:app
```

By default the app serves on port `5000`.

## Deploy on Oracle Linux

This is a minimal systemd + nginx + certbot flow.

1. Install system dependencies (Python 3.11+, nginx, certbot) and clone this repo.
2. Create a dedicated service user (for example `gunicorn`) and virtual environment.
3. Install Python dependencies from `src/requirements.txt`.
4. Configure environment variables (recommended via systemd `Environment=` entries or `EnvironmentFile=`).
5. Create a `gunicorn.service` unit that runs from `src/`:

   ```ini
   [Unit]
   Description=OCI Management Portal (gunicorn)
   After=network.target

   [Service]
   User=gunicorn
   Group=nginx
   WorkingDirectory=/opt/oci-management-portal/src
   ExecStart=/opt/oci-management-portal/.venv/bin/gunicorn -c gunicorn.config.py wsgi:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

6. Configure nginx as reverse proxy to Gunicorn (unix socket or localhost TCP).
7. Enable TLS with certbot:

   ```bash
   sudo certbot --nginx -d your.domain.example
   ```

8. Enable and start services:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now gunicorn
   sudo systemctl enable --now nginx
   ```

## Build and Run with Docker

Build image from repository root:

```bash
docker build -t oci-management-portal:latest .
```

Run container:

```bash
docker run --rm -p 5000:5000 --env-file sample.env oci-management-portal:latest
```

If running behind ingress/load balancer, set `OCI_MGMT_DASH_PROXY=true`.

## Opening Issues

Please use GitHub Issues: <https://github.com/flynnkc/oci-management-portal/issues>

When filing a bug, include:
- clear summary
- environment details (local/docker/oracle linux)
- exact steps to reproduce
- expected behavior vs actual behavior
- relevant logs, stack traces, or screenshots

For feature requests, include the use case, expected outcome, and any OCI constraints.

## Contributing

Contributions are welcome.

1. Fork the repository and create a feature branch.
2. Keep changes focused and scoped to one logical improvement.
3. Validate your changes locally (Flask/Gunicorn or Docker path).
4. Open a pull request with:
   - problem statement
   - implementation summary
   - testing/validation notes
   - screenshots (if UI behavior changed)

Please keep commit messages clear and descriptive, and reference related issue numbers when possible.
