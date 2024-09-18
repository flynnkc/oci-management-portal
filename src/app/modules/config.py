#!/usr/bin/python3.11

import configparser
import os

class Configuration:
    """Configuration is the object that takes in arguments and options from various
       sources and turns them into an application configuration. This is intended
       to centralize all configurations and modes to conveying configuration data
       into a single place.

       Order of precedence for configuration information:
       1. Configuration file
       2. Command line arguments
       3. Environment variables
    """
    
    def __init__(self, file=None, **kwargs):
        # Dictionaries for property storage
        self.app: dict = {}
        self.auth: dict = {}
        self.idm: dict = {}
        self.logging: dict = {}

        if file: self.parse_ini(file)
        
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

    def parse_ini(self, file: str | os.PathLike):
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

    def parse_env(self):
        pass

    def parse_secrets(self, secret_id: list[str]):
        pass
