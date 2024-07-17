#!/usr/python3.11

import logging
from http import HTTPStatus

from oci.analytics import AnalyticsClient
from oci.bastion import BastionClient
from oci.core import BlockstorageClient, ComputeClient
from oci.oda import OdaClient
from oci.database import DatabaseClient
from oci.integration import IntegrationInstanceClient

# Deleter will handle delete operations providing a central class to process
# resource terminations
class Deleter:
    def __init__(self, config, signer, log_level=logging.INFO):
        self.config = config
        self.signer = signer

        # Clients start empty and are initialized as needed
        self.analytics_client: AnalyticsClient | None = None
        self.bastion_client: BastionClient | None = None
        self.blockstorage_client: BlockstorageClient | None = None
        self.oda_client: OdaClient | None = None
        self.database_client: DatabaseClient | None = None
        self.instance_client: ComputeClient | None = None
        self.integration_client: IntegrationInstanceClient | None = None

        # Start logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.logger.addHandler(handler)
        self.logger.debug('Created Deleter')

        # Use this dictionary to select the correct method for resource type
        self.control = {
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

    # terminate checks a resources against the control tree and runs the function
    # if it has been implemented, passing all args as kwargs
    def terminate(self, resource: dict) -> int:
        self.logger.info(f'Request to delete {resource["resource_type"]}: '
                      f'{resource["identifier"]}')
        try:
            terminate_func = self.control[resource['resource_type']]
            self.logger.debug(f'Calling {terminate_func.__name__}')
            return terminate_func(**resource)
        except KeyError:
            self.logger.info(f'Resource type {resource["identifier"]} not supported')
            return HTTPStatus.NOT_IMPLEMENTED
        
    def terminate_analytics_instance(self, **kwargs) -> int:
        if not self.analytics_client:
            self.analytics_client = AnalyticsClient(self.config, signer=self.signer)

        return self.analytics_client.delete_analytics_instance(
            kwargs.get('identifier')).status

    def terminate_instance(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        return self.instance_client.terminate_instance(
            kwargs.get('identifier')).status
    
    def terminate_dedicated_vm(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        return self.instance_client.delete_dedicated_vm_host(
            kwargs.get('identifier')).status
    
    def terminate_image(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        return self.instance_client.delete_image(kwargs.get('identifier')).status
        
    def terminate_boot_volume(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_boot_volume(
            kwargs.get('identifier')).status
    
    def terminate_boot_volume_backup(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_boot_volume_backup(
            kwargs.get('identifier')).status
    
    def terminate_volume(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_volume(
            kwargs.get('identifier')).status
    
    def terminate_volume_backup(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_volume_backup(
            kwargs.get('identifier')).status
    
    def terminate_volume_backup_policy(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_volume_backup_policy(
            kwargs.get('identifier')).status
    
    def terminate_volume_group(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_volume_group(
            kwargs.get('identifier')).status
    
    def terminate_volume_group_backup(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        return self.blockstorage_client.delete_volume_group_backup(
            kwargs.get('identifier')).status
    
    def terminate_autonomousdatabase(self, **kwargs) -> int:
        if not self.autonomousdatabase_client:
            self.database_client = DatabaseClient(self.config, signer=self.signer)
            
        return self.database_client.delete_autonomous_database(
            kwargs.get('identifier')).status
    
    def terminate_dbsystem(self, **kwargs) -> int:
        if not self.database_client:
            self.database_client = DatabaseClient(self.config, signer=self.signer)

        return self.database_client.terminate_db_system(
            kwargs.get('identifier')).status
    
    def terminate_integration_instance(self, **kwargs) -> int:
        if not self.integration_client:
            self.integration_client = IntegrationInstanceClient(self.config,
                                                                signer=self.signer)
            
        return self.integration_client.delete_integration_instance(
            kwargs.get('identifier')).status
    
    def terminate_bastion(self, **kwargs) -> int:
        if not self.bastion_client:
            self.bastion_client = BastionClient(self.config, signer=self.signer)

        return self.bastion_client.delete_bastion(kwargs.get('identifier')).status
    
    # This doesn't appear to be supported by search, so can't be used yet
    def terminate_session(self, **kwargs) -> int:
        if not self.bastion_client:
            self.bastion_client = BastionClient(self.config, signer=self.signer)

        return self.bastion_client.delete_session(kwargs.get('identifier')).status
    
    def terminate_oda_instance(self, **kwargs) -> int:
        if not self.oda_client:
            self.oda_client = OdaClient(self.config, signer=self.signer)

        return self.oda_client.delete_oda_instance(kwargs.get('identifier')).status