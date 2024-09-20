#!/usr/python3.11

import logging
from http import HTTPStatus

from .client_bundle import ClientBundle
from ..utils import log_factory


class Deleter:
    """Deleter will handle delete operations providing a central class to process
       resource terminations.
    """

    def __init__(self, config,
                 signer,
                 handler=logging.StreamHandler(),
                 log_level=logging.INFO,
                 regions: list[str] | None=None):
        
        # Logging
        self.logger = log_factory(__name__, log_level, handler)

        # Authentication variables
        self.config = config
        self.signer = signer

        # Dictionary of client bundles
        self.clients: dict[str, ClientBundle] = self.create_clients(regions)

        # Use this dictionary to select the correct method for resource type
        self.control_tree = {
            'AnalyticsInstance': self.terminate_analytics_instance,
            'Instance': self.terminate_instance,
            'DedicatedVmHost': self.terminate_dedicated_vm,
            'Image': self.terminate_image,
            'BootVolume': self.terminate_boot_volume,
            'BootVolumeBackup': self.terminate_boot_volume_backup,
            'Volume': self.terminate_volume,
            'VolumeBackup': self.terminate_volume_backup,
            'VolumeBackupPolicy': self.terminate_volume_backup_policy,
            'VolumeGroup': self.terminate_volume_group,
            'VolumeGroupBackup': self.terminate_volume_group_backup,
            'AutonomousDatabase': self.terminate_autonomousdatabase,
            'DbSystem': self.terminate_dbsystem,
            'IntegrationInstance': self.terminate_integration_instance,
            'Bastion': self.terminate_bastion,
            'OdaInstance': self.terminate_oda_instance
        }

        self.logger.info('Deleter initialized')

    def create_clients(self, regions: list[str] | None) -> dict[str, ClientBundle]:
        clients = {}

        # Use single bundle with region in config if regions not passed
        if not regions:
            clients[self.config['region']] = ClientBundle(self.config, self.signer)
        else:
            for region in regions:
                self.config['region'] = region
                self.signer.region = region
                clients[region] = ClientBundle(self.config, self.signer)

        return clients

    # terminate checks a resources against the control tree and runs the function
    # if it has been implemented, passing all args as kwargs
    def terminate(self, resource: dict, **kwargs) -> int:
        self.logger.info(f'Request to delete {resource["resource_type"]}: '
                      f'{resource["identifier"]} in '
                      f'{kwargs.get("region", "undefined region")}')
        
        try:
            terminate_func = self.control_tree[resource['resource_type']]
            self.logger.debug(f'Calling {terminate_func.__name__}')
            return terminate_func(**resource, **kwargs)
        except KeyError:
            self.logger.info(f'Resource type {resource["resource_type"]} not supported')
            return HTTPStatus.NOT_IMPLEMENTED
        
    """Terminate_resource methods have the signature:
       terminate_xyz(self, identifier: str=None, region: str=None, **kwargs).
       Terminate passes keyword arguments for identifier, region, and any optional
       values to the terminate_resource method, which keeps methods uniform.
    """

    def terminate_analytics_instance(self, identifier: str=None, region: str=None,
                                     **kwargs) -> int:
        return self.clients[region].analytics_client.delete_analytics_instance(
            identifier).status

    def terminate_instance(self, identifier: str=None, region: str=None,
                           **kwargs) -> int:
        # Delete instance but not boot volume by default
        return self.clients[region].compute_client.terminate_instance(identifier,
            preserve_boot_volume=kwargs.get('preserve_boot_volume', True)).status
    
    def terminate_dedicated_vm(self, identifier: str=None, region:str=None,
                               **kwargs) -> int:
        return self.clients[region].compute_client.delete_dedicated_vm_host(
            identifier).status
    
    def terminate_image(self, identifier: str=None, region: str=None, **kwargs) -> int:
        return self.clients[region].compute_client.delete_image(identifier).status
        
    def terminate_boot_volume(self, identifier: str=None, region: str=None,
                              **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_boot_volume(
            identifier).status
    
    def terminate_boot_volume_backup(self, identifier: str=None, region: str=None,
                                     **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_boot_volume_backup(
            identifier).status
    
    def terminate_volume(self, identifier: str=None, region: str=None,
                         **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_volume(
            identifier).status
    
    def terminate_volume_backup(self, identifier: str=None, region: str=None,
                                **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_volume_backup(
            identifier).status
    
    def terminate_volume_backup_policy(self, identifier: str=None, region: str=None,
                                       **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_volume_backup_policy(
            identifier).status
    
    def terminate_volume_group(self, identifier: str=None, region: str=None,
                               **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_volume_group(
            identifier).status
    
    def terminate_volume_group_backup(self, identifier: str=None, region: str=None,
                                      **kwargs) -> int:
        return self.clients[region].blockstorage_client.delete_volume_group_backup(
            identifier).status
    
    def terminate_autonomousdatabase(self, identifier: str=None, region: str=None,
                                     **kwargs) -> int:
        return self.clients[region].database_client.delete_autonomous_database(
            identifier).status
    
    def terminate_dbsystem(self, identifier: str=None, region: str=None,
                           **kwargs) -> int:
        return self.clients[region].database_client.terminate_db_system(
            identifier).status
    
    def terminate_integration_instance(self, identifier: str=None, region: str=None,
                                       **kwargs) -> int:
        return self.clients[region].integration_client.delete_integration_instance(
            identifier).status
    
    def terminate_bastion(self, identifier: str=None, region: str=None,
                          **kwargs) -> int:
        return self.clients[region].bastion_client.delete_bastion(identifier).status
    
    # This doesn't appear to be supported by search, so can't be used yet
    def terminate_session(self, identifier: str=None, region: str=None,
                          **kwargs) -> int:
        return self.clients[region].bastion_client.delete_session(identifier).status
    
    def terminate_oda_instance(self, identifier: str=None, region: str=None,
                               **kwargs) -> int:
        return self.clients[region].oda_client.delete_oda_instance(identifier).status