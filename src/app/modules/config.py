#!/usr/bin/python3.11

import configparser
import logging
import logging.handlers

from oci.config import DEFAULT_LOCATION, DEFAULT_PROFILE
from os import PathLike, getenv


class Configuration:
    """
    Central configuration loader.
    Environment variables + optional ini file.
    """

    def __init__(self, file=None, prefix="OCIDOMAIN", **kwargs):
        self.app = {
            "uri": "http://localhost:5000",
        }

        self.auth = {
            "authtype": "profile",
            "configfile": "~/.oci/config",
            "profile": "DEFAULT",
        }

        self.idm = {}

        self.logging = {
            "loglevel": "info",
            "logformat": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        }

        
        self.parse_env(prefix)

        if file:
            self.parse_ini(file)

        # Default filter namespace = tag namespace if not set
        self.app["filternamespace"] = self.app.get(
            "filternamespace", self.app.get("tagnamespace")
        )

        
        for d in (self.app, self.auth, self.idm, self.logging):
            for k, v in d.items():
                setattr(self, k, v)

        
        self.handler = self._create_handler()

    def __repr__(self):
        return (
            "Configuration:\n"
            f"\tApp Settings - {self.app}\n"
            f"\tAuthentication Settings - {self.auth}\n"
            f"\tIdentity Management Settings - {self.idm}\n"
            f"\tLogging Settings - {self.logging}"
        )

    
    def parse_ini(self, file: str | PathLike):
        parser = configparser.ConfigParser(inline_comment_prefixes=["#"])
        parser.read(file)

        for section in parser.sections():
            values = dict(parser.items(section))
            if section == "APP":
                self.app |= values
            elif section == "AUTH":
                self.auth |= values
            elif section == "IDM":
                self.idm |= values
            elif section == "LOGGING":
                self.logging |= values

    def parse_env(self, PREFIX: str):
        # Read Values from Env File
        if getenv(f"{PREFIX}_IDM_ENDPOINT"):
            self.idm["endpoint"] = getenv(f"{PREFIX}_IDM_ENDPOINT")
        if getenv(f"{PREFIX}_CLIENT_ID"):
            self.idm["clientid"] = getenv(f"{PREFIX}_CLIENT_ID")
        if getenv(f"{PREFIX}_CLIENT_SECRET"):
            self.idm["clientsecret"] = getenv(f"{PREFIX}_CLIENT_SECRET")

        
        if getenv(f"{PREFIX}_TAG_NAMESPACE"):
            self.app["tagnamespace"] = getenv(f"{PREFIX}_TAG_NAMESPACE")
        if getenv(f"{PREFIX}_TAG_KEY"):
            self.app["tagkey"] = getenv(f"{PREFIX}_TAG_KEY")
        if getenv(f"{PREFIX}_FILTER_NAMESPACE"):
            self.app["filternamespace"] = getenv(f"{PREFIX}_FILTER_NAMESPACE")
        if getenv(f"{PREFIX}_FILTER_KEY"):
            self.app["filterkey"] = getenv(f"{PREFIX}_FILTER_KEY")

        
        self.app["uri"] = getenv(f"{PREFIX}_APP_URI", self.app["uri"])

    
        self.auth["authtype"] = getenv(f"{PREFIX}_AUTH_TYPE", self.auth["authtype"])
        self.auth["profile"] = getenv(f"{PREFIX}_PROFILE", DEFAULT_PROFILE)
        self.auth["configfile"] = getenv(f"{PREFIX}_LOCATION", DEFAULT_LOCATION)

        
        self.logging["loglevel"] = getenv(
            f"{PREFIX}_LOG_LEVEL", self.logging["loglevel"]
        )
        self.logging["logformat"] = getenv(
            f"{PREFIX}_LOG_FORMAT", self.logging["logformat"]
        )

    
    #Enable  Logging
    
    def get_log_level(self) -> str:
        return self.loglevel.upper()

    def set_log_level(self, level: str | int):
        self.loglevel = level

    def get_log_handler(self) -> logging.Handler:
        return self.handler

    def set_log_handler(self, handler: logging.Handler):
        self.handler = handler

    def _create_handler(self) -> logging.Handler:
        handler = logging.StreamHandler()
        handler.setLevel(self.get_log_level())
        handler.setFormatter(logging.Formatter(self.logformat))
        return handler

