#!/usr/bin/python3.11

import logging

from secrets import token_urlsafe
from .config import Configuration

# Generate a dict of random tokens and return it
def generate_csrf_tokens(n: int) -> dict:
    tokens = {}

    for i in range(n):
        tokens[token_urlsafe()] = None

    return tokens

def log_factory(name: str, log_level: int | str,
                handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(log_level)

    return logger
