#/usr/bin/python3.11

import datetime
import logging

from oci import identity
from oci import pagination
from oci.signer import Signer

class TagUpdater:
    def __init__(self, config: dict, compartments: list[str], signer: Signer=None):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.compartments = compartments
        self.client = identity.IdentityClient(config, signer=signer)

    # Tag change behavior defined here
    def update_tags(self, namespace: str, key: str):
        for default in self.get_tag_defaults(namespace, key):
            details = identity.models.UpdateTagDefaultDetails(
                is_required=default.is_required,
                value=self.get_value()
            )

            self.log.info(f'Updating tag default {default.id} with {details.value}')

            response = self.client.update_tag_default(default.id, details)
            if response.status != 200:
                self.log.error(f'Non-200 status code trying to update {default.id}')


    # Change this method to determine tag value
    def get_value(self) -> str:
        ### Change here ###

        # I want to set the tag to a date in the format yyyy-mm-dd
        date = datetime.date.today() + datetime.timedelta(days=90)
        return date.strftime('%Y-%m-%d')
    
        ### End changes ###

    # Return list of applicable tag defaults
    def get_tag_defaults(self, namespace: str, key: str) -> list[object]:
        ns_id = self.get_tag_namespace(namespace)

        defaults = []
        for cmp in self.compartments:
            response = pagination.list_call_get_all_results(
                self.client.list_tag_defaults, compartment_id=cmp)
            
            for result in response.data:
                if result.tag_definition_name == key and result.tag_namespace_id == ns_id:
                    defaults.append(result)

        return defaults

    # Get the tag namespace OCID
    def get_tag_namespace(self, namespace) -> str:
        response = pagination.list_call_get_all_results(
            self.client.list_tag_namespaces,
            self.config['tenancy'],
            include_subcompartments=True
        )

        for item in response.data:
            if item.name == namespace:
                return item.id
