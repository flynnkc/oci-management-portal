# OCI Management Portal

OCI Management Portal is a Flask web application for discovering and managing OCI resources tagged for ownership and lifecycle control. It supports authenticated user views, search/filter flows, resource expiry extension, and managed delete workflows.

Use this README to configure, run locally (Flask or Gunicorn), deploy on Oracle Linux, or build and run the container image.

## Project Dependencies

This section lists the runtime prerequisites needed to start the app.

### Python

- **Required Python version:** `3.11+`
- The project Docker image is built from `python:3.11-slim`, and local examples use `python3.11`.

### Required top-level Python packages

Install with:

```bash
pip install -r src/requirements.txt
```

Core direct dependencies used by this app:

- `Flask` – web application framework
- `Flask-Session` – server-side session management
- `cachelib` – filesystem cache backend used by session handling
- `redis` – shared session backend for Redis/Valkey deployments
- `oci` – Oracle Cloud Infrastructure Python SDK
- `requests` – HTTP calls for OIDC token and userinfo/introspection flows
- `PyJWT` – ID token decode/validation (`import jwt`)
- `gunicorn` – WSGI server for production/prod-like runs

All pinned package versions (including transitive support libs) are in `src/requirements.txt`.

### Other runtime requirements

- **OCI access configuration** (auth mode + credentials), via environment variables documented in [Configuration](#configuration)
- **Identity Domain / OIDC app** values (`OCI_MGMT_DASH_IDM_ENDPOINT`, `OCI_MGMT_DASH_CLIENT_ID`, `OCI_MGMT_DASH_CLIENT_SECRET`)
- **Tag/filter configuration** (`OCI_MGMT_DASH_TAG_NAMESPACE`, `OCI_MGMT_DASH_TAG_KEY`, `OCI_MGMT_DASH_FILTER_KEY`, etc.)
- **Session backend requirement:**
  - `filesystem` (default) for single-node use, or
  - Redis/Valkey plus `OCI_MGMT_DASH_SESSION_REDIS_URL` for multi-pod/shared sessions
- **For Docker run path:** Docker/Podman runtime available locally

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
| `OCI_MGMT_DASH_USER_SCOPED_OCI_CALLS` | No | `true` | When `true`, Search/Delete/Extend/WorkRequest calls execute with per-user OCI token exchange signer (UPST signer cache is local process memory only). |
| `OCI_MGMT_DASH_TOKEN_EXCHANGE_ENABLED` | No | `true` | Enables OCI SDK `TokenExchangeSigner` flow for user-scoped OCI calls. |
| `OCI_MGMT_DASH_TOKEN_EXCHANGE_EXPIRY_SKEW_SECONDS` | No | `60` | Expiry skew used before considering session access token expired for exchange. |
| `OCI_MGMT_DASH_LOG_LEVEL` | No | `info` | Application log level (`debug`, `info`, etc.). |
| `OCI_MGMT_DASH_LOG_FORMAT` | No | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | Python logging format string. |

> Tip: Start from `sample.env`, update values for your tenancy/domain, then source it before running.

### OIDC session handling

During login callback, the app validates the ID token and performs login-time access-token introspection to enrich/confirm user context. It then stores only minimal user session data (`user`, `email`, `domain`, `sub`) and does **not** persist access tokens in the session.

> Note: When `OCI_MGMT_DASH_USER_SCOPED_OCI_CALLS=true`, the app stores OIDC access-token session material server-side only (filesystem/redis/valkey session backend) to supply OCI SDK `TokenExchangeSigner`. No bearer token material is exposed to browser storage.
>
> UPST signer cache for token exchange is **process-local only** (in-memory) and is not shared through Redis/Valkey.

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

### UPST operational requirements (user-scoped OCI calls)

When `OCI_MGMT_DASH_USER_SCOPED_OCI_CALLS=true`, the token-exchange signer cache is local to each Gunicorn worker process. For reliable behavior:

1. Configure **sticky session affinity** at the ingress/load balancer.
2. Prefer **one Gunicorn worker per pod** and scale horizontally at pod level.
3. Expect signer re-creation after pod/worker restart or occasional affinity breaks.

Running multiple Gunicorn workers is supported, but cache misses across workers can introduce
extra token-exchange calls and therefore latency jitter. This is primarily a performance
consistency tradeoff, not typically a correctness/session-integrity failure.

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

Defaults in `src/gunicorn.config.py` are tuned for UPST local-cache behavior:
- `workers=1`
- `worker_class=gthread`
- `threads=4`
- env-driven overrides (`GUNICORN_*`) for deployment tuning

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
