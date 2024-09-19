#!/usr/bin/python3.11

import logging
from secrets import token_urlsafe

from .config import Configuration

DEFAULT_FORMATTER = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Generate a dict of random tokens and return it
def generate_csrf_tokens(n: int) -> dict:
    tokens = {}

    for i in range(n):
        tokens[token_urlsafe()] = None

    return tokens

def log_factory(name: str, cfg: Configuration | dict={}) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(cfg.get('log_level', logging.INFO))

    handler_func = cfg.get('log_handler', logging.StreamHandler)
    handler = handler_func()
    handler.setLevel(cfg.get('log_level', logging.INFO))
    handler.setFormatter(cfg.get('log_formatter', DEFAULT_FORMATTER))

    logger.addHandler(handler)
    
    return logger
