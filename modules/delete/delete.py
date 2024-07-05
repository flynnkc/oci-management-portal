#!/usr/python3.11

from http import HTTPStatus

from oci.core import ComputeClient

# Deleter will handle delete operations providing a central class to process
# resource terminations
class Deleter:
    def __init__(self, config, signer):
        self.config = config
        self.signer = signer
        self.instance_client: ComputeClient | None = None

        # Use this dictionary to select the correct method for resource type
        self.control = {
            'Instance': self.delete_instance
        }

    # terminate checks a resources against the control tree and runs the function
    # if it has been implemented, passing all args as kwargs
    def terminate(self, resource: object) -> int:
        try:
            delete_func = self.control[resource.type]
            return delete_func(**resource)
        except KeyError:
            return HTTPStatus.NOT_IMPLEMENTED

    # Terminate instance resources
    def delete_instance(self, **kwargs) -> int:
        if not self.instance_client:
            self.instance_client = ComputeClient(self.config, signer=self.signer)

        result = self.instance_client.terminate_instance(kwargs.get('identifier'))

        return result.status
        