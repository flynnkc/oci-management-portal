#!/usr/bin/python3.11
# Configuration file for gunicorn server

import multiprocessing

bind = "unix:/run/gunicorn/gunicorn.sock"

workers = multiprocessing.cpu_count() * 2 + 1

loglevel = "info"
#accesslog = "/var/log/gunicorn/access.log"
#errorlog = "/var/log/gunicorn/error.log"
#capture_output = True

max_requests = 1000
max_requests_jitter = 50