#!/usr/python3.11

import logging

from os import getenv
from oci import Signer
from oci.config import from_file, get_config_value_or_default, DEFAULT_LOCATION, DEFAULT_PROFILE
from oci.auth import signers

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handler.setLevel(logging.INFO)
log.addHandler(handler)

# Signer entrypoint, this function should choose and return a tuple containing
# a config dict and a signer
def create_signer(authentication_type: str | None=None,
                **kwargs) -> tuple[dict, Signer]:
    func = {
        'profile': create_profile_signer,
        'instance_principal': create_instance_principal_signer,
        'delegation_token': create_delegation_token_signer,
        'workload_principal': create_workload_principal_signer
    }

    try:
        signer_func = func[authentication_type.lower()]
        return signer_func(**kwargs)
    except KeyError:
        log.warn(f'Invalid signer type: {authentication_type}')
        log.warn('Attempting to use default profile signer')
        return create_profile_signer()

# Default profile signer, looks in ~/.oci/config for DEFAULT profile unless given
# arguments for profile and location.
def create_profile_signer(profile: str=DEFAULT_PROFILE,
                          location: str=DEFAULT_LOCATION, **kwargs) -> tuple[dict, Signer]:
    log.info(f'Using profile {profile} at {location} for authentication')
    config = from_file(file_location=location, profile_name=profile)
    signer = Signer(
        tenancy=config["tenancy"],
        user=config["user"],
        fingerprint=config["fingerprint"],
        private_key_file_location=config.get("key_file"),
        pass_phrase=get_config_value_or_default(config, "pass_phrase"),
        private_key_content=config.get("key_content")
    )
    return config, signer

# Signer for instance principal authentication within OCI
def create_instance_principal_signer(**kwargs):
    log.info('Using instance principal for authentication')
    try:
        signer = signers.InstancePrincipalsSecurityTokenSigner()
        cfg = {'region': signer.region, 'tenancy': signer.tenancy_id}
        log.debug(f'Instance Principal signer created: {signer}\nConfig: {cfg}')
        return cfg, signer
    
    except Exception as e:
        log.error(f'Instance Principal signer failed due to exception {e}')
        raise SystemExit

# Cloud Shell signer, not recommended
def create_delegation_token_signer(**kwargs) -> tuple[dict, Signer]:
    log.info('Using delegation token for authentication')
    try:
        # Environment variables present in OCI Cloud Shell
        env_config_file = getenv('OCI_CONFIG_FILE')
        env_config_section = getenv('OCI_CONFIG_PROFILE')

        if not env_config_file or not env_config_section:
            log.error('Missing delegation token configuration')
            raise SystemExit

        config = from_file(env_config_file, env_config_section)
        delegation_token_location = config["delegation_token_file"]

        with open(delegation_token_location, 'r') as delegation_token_file:
            delegation_token = delegation_token_file.read().strip()
            signer = signers.InstancePrincipalsDelegationTokenSigner(delegation_token=delegation_token)

            return config, signer
    except KeyError as e:
        log.error(f'Key Error exception during Delegation Token retrieval {e}')
        raise SystemExit
    except Exception as e:
        log.error(f'Exception during Delegation Token retrieval {e}')
        raise SystemExit
    
# Function to create workload identity signer for use by Oracle Kubernetes Engine
def create_workload_principal_signer(**kwargs) -> tuple[dict, Signer]:
    log.info('Using OKE Workload Auth Signer')
    try:
        signer = signers.get_oke_workload_identity_resource_principal_signer()
        cfg = {'region': signer.region, 'tenancy': signer.tenancy_id}
        log.debug(f'Workload Principal signer created: {signer}\nConfig: {cfg}')
        return cfg, signer
    except Exception as e:
        log.error(f'Workload Principal signer failed due to exception {e}')
        raise SystemExit
