#!/usr/bin/python3.11

import os
import logging

from secrets import token_urlsafe

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
