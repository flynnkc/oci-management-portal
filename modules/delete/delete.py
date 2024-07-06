#!/usr/python3.11

import logging
from http import HTTPStatus

from oci.core import BlockstorageClient, ComputeClient

# Deleter will handle delete operations providing a central class to process
# resource terminations
class Deleter:
    def __init__(self, config, signer, log_level=logging.INFO):
        self.config = config
        self.signer = signer

        # Clients start empty and are initialized as needed
        self.instance_client: ComputeClient | None = None
        self.blockstorage_client: BlockstorageClient | None = None

        # Start logger
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        self.log.addHandler(handler)
        self.log.debug('Created Deleter')

        # Use this dictionary to select the correct method for resource type
        self.control = {
            'Instance': self.terminate_instance,
            'Image': self.terminate_image,
            'BootVolume': self.terminate_boot_volume,
            'Volume': self.terminate_volume
        }

    # terminate checks a resources against the control tree and runs the function
    # if it has been implemented, passing all args as kwargs
    def terminate(self, resource: dict) -> int:
        self.log.info(f'Request to delete {resource["resource_type"]}: '
                      f'{resource["identifier"]}')
        try:
            terminate_func = self.control[resource['resource_type']]
            return terminate_func(**resource)
        except KeyError:
            return HTTPStatus.NOT_IMPLEMENTED

    # Terminate instance resources
    def terminate_instance(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        result = self.instance_client.terminate_instance(kwargs.get('identifier'))

        return result.status
    
    def terminate_image(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        result = self.instance_client.delete_image(kwargs.get('identifier'))

        return result.status
        
    def terminate_boot_volume(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        result = self.blockstorage_client.delete_boot_volume(kwargs.get('identifier'))

        return result.status
    
    def terminate_volume(self, **kwargs) -> int:
        if not self.blockstorage_client:
            self.blockstorage_client = BlockstorageClient(self.config,
                                                          signer=self.signer)
            
        result = self.blockstorage_client.delete_volume(kwargs.get('identifier'))

        return result.status