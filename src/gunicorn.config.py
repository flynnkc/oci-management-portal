#!/usr/bin/python3.11
# Configuration file for gunicorn server

import os

# Bind to container-friendly TCP listener by default.
bind = os.getenv('GUNICORN_BIND', '0.0.0.0:5000')

# Keep a single worker by default so process-local UPST signer cache remains
# consistent for sticky-session traffic. Scale horizontally at pod level.
workers = int(os.getenv('GUNICORN_WORKERS', '1'))

# Threaded worker improves concurrency without breaking per-process cache.
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
threads = int(os.getenv('GUNICORN_THREADS', '4'))

loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')
capture_output = True

# Recycle workers periodically to reduce long-lived process risk.
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# OCI operations may run long when polling work requests.
timeout = int(os.getenv('GUNICORN_TIMEOUT', '600'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '60'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
