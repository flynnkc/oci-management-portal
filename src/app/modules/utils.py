#!/usr/bin/python3.11

import os
import logging

from secrets import token_urlsafe

# Generate a dict of random tokens and return it
def generate_csrf_tokens(n: int) -> dict:
    tokens = {}

    for i in range(n):
        tokens[token_urlsafe()] = None

    return tokens

def log_factory(name: str,
                log_level: int | str=os.getenv('LOG_LEVEL', logging.INFO),
                handler: logging.Handler | None = None,
                **kwargs) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    
    # StreamHandler as default
    if not handler: handler = logging.StreamHandler()

    logger.addHandler(handler)
    logger.setLevel(log_level)

    return logger
