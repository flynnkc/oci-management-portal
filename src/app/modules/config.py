#!/usr/bin/python3.11

import configparser

from oci.config import DEFAULT_LOCATION, DEFAULT_PROFILE
from os import PathLike, getenv

class Configuration:
    """Configuration is the object that takes in arguments and options from various
       sources and turns them into an application configuration. This is intended
       to centralize all configurations and modes to conveying configuration data
       into a single place.

       Order of precedence for configuration information:
       1. Configuration file
       2. Environment variables
    """
    
    def __init__(self, file=None, prefix='OCIDOMAIN', **kwargs):
        # Dictionaries for property storage with defaults
        self.app: dict = {
            'uri': 'http://localhost:5000',
            }
        self.auth: dict = {
            'authtype': 'profile',
            'configfile': '~/.oci/config',
            'profile': 'DEFAULT'
        }
        self.idm: dict = {}
        self.logging: dict = {
            'loglevel': 'info'
        }

        # Parsers
        self.parse_env(prefix)
        if file: self.parse_ini(file)

        # Check if flilter namespace was provided, set to tag namespace if empty
        self.app['filternamespace'] = self.app.get('filternamespace',
                                                   self.app['tagnamespace'])
        
        # Set attributes as properties
        for dictionary in [self.app, self.auth, self.idm, self.logging]:
            for key in dictionary:
                setattr(self, key, dictionary[key])

    def __repr__(self):
        return ('Configuration:\n'
                f'\tApp Settings - {self.app}\n'
                f'\tAuthentication Settings - {self.auth}\n'
                f'\tIdentity Management Settings - {self.idm}\n'
                f'\tLogging Settings - {self.logging}')

    def parse_ini(self, file: str | PathLike):
        parser = configparser.ConfigParser()
        parser.read(file)
        
        sections = {}
        for section in parser.sections():
            sections[section] = dict(parser.items(section))

        try:
            self.app = self.app | sections['APP']
            self.auth = self.auth | sections['AUTH']
            self.idm = self.idm | sections['IDM']
            self.logging = self.logging | sections['LOGGING']
        except KeyError:
            pass

    def parse_env(self, PREFIX: str):
        app = {}
        auth = {}
        idm = {}
        logging = {}

        # Need add only varibles that are set to prevent previous settings from
        # being overwritten by None type
        if getenv(f'{PREFIX}_IDM_ENDPOINT'): idm['endpoint'] = getenv(
            f'{PREFIX}_IDM_ENDPOINT')
        if getenv(f'{PREFIX}_CLIENT_ID'): idm['clientid'] = getenv(
            f'{PREFIX}_CLIENT_ID')
        if getenv(f'{PREFIX}_TAG_NAMESPACE'): app['tagnamespace'] = getenv(
            f'{PREFIX}_TAG_NAMESPACE')
        if getenv(f'{PREFIX}_TAG_KEY'): app['tagkey'] = getenv(f'{PREFIX}_TAG_KEY')
        if getenv(f'{PREFIX}_FILTER_NAMESPACE'): app['filternamespace'] = getenv(
            f'{PREFIX}_FILTER_NAMESPACE')
        if getenv(f'{PREFIX}_FILTER_KEY'): app['filterkey'] = getenv(
            f'{PREFIX}_FILTER_KEY')
        if getenv(f'{PREFIX}_LOG_FILE'): logging['logfile'] = getenv(
            f'{PREFIX}_LOG_FILE')
        if getenv(f'{PREFIX}_ERR_LOG_FILE'): logging['errorlogfile'] = getenv(
            f'{PREFIX}_ERR_LOG_FILE')

        # Variables with defaults
        app['uri'] = getenv(f'{PREFIX}_APP_URI', 'http://localhost:5000')
        auth['authtype'] = auth_type = getenv(f'{PREFIX}_AUTH_TYPE', 'profile')
        auth['profile'] = getenv(f'{PREFIX}_PROFILE', DEFAULT_PROFILE)
        auth['configfile'] = getenv(f'{PREFIX}_LOCATION', DEFAULT_LOCATION)
        logging['loglevel'] = getenv(f'{PREFIX}_LOG_LEVEL', 'info')

        # Union
        self.app = self.app | app
        self.auth = self.auth | auth
        self.idm = self.idm | idm
        self.logging = self.logging | logging

    def parse_secrets(self, secret_id: list[str]):
        pass
