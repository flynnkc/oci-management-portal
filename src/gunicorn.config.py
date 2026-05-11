#!/usr/bin/python3.11
# Configuration file for gunicorn server

import multiprocessing

bind = "unix:/run/gunicorn/gunicorn.sock"

bind = "0.0.0.0:5000"

workers = multiprocessing.cpu_count() * 2

loglevel = "info"

max_requests = 1000
max_requests_jitter = 50
timeout = 600 # Default OCI retry limit
graceful_timeout = 60
