#!/usr/python3.11

from oci.analytics import AnalyticsClient
from oci.bastion import BastionClient
from oci.core import BlockstorageClient, ComputeClient
from oci.oda import OdaClient
from oci.database import DatabaseClient
from oci.integration import IntegrationInstanceClient

class ClientBundle:
    """ClientBundle is mean to bundle various OCI clients.
    """

    def __init__(self, config, signer):
        self.analytics_client = AnalyticsClient(config, signer=signer)
        self.bastion_client = BastionClient(config, signer=signer)
        self.blockstorage_client = BlockstorageClient(config, signer=signer)
        self.compute_client = ComputeClient(config, signer=signer)
        self.oda_client = OdaClient(config, signer=signer)
        self.database_client = DatabaseClient(config, signer=signer)
        self.integration_client = IntegrationInstanceClient(config,
                                                                   signer=signer)