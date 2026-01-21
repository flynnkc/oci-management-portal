from copy import deepcopy

from oci.analytics import AnalyticsClient
from oci.bastion import BastionClient
from oci.core import BlockstorageClient, ComputeClient
from oci.database import DatabaseClient
from oci.functions import FunctionsManagementClient
from oci.integration import IntegrationInstanceClient
from oci.logging import LoggingManagementClient
from oci.oda import OdaClient
from oci.object_storage import ObjectStorageClient
from oci.resource_manager import ResourceManagerClient
from oci.devops import DevopsClient
from oci.identity import IdentityClient    

class ClientBundle:
    """
    ClientBundle bundles all OCI SDK clients used by MOVE (quarantine) logic.
    Design principles:
    - One bundle per region
    - Immutable config per bundle
    - Only SDK-supported, stable clients
    """
    def __init__(self, config, signer):
        cfg = deepcopy(config)
        self.compute_client = ComputeClient(cfg, signer=signer)
        self.blockstorage_client = BlockstorageClient(cfg, signer=signer)
        self.database_client = DatabaseClient(cfg, signer=signer)
        self.analytics_client = AnalyticsClient(cfg, signer=signer)
        self.integration_client = IntegrationInstanceClient(cfg, signer=signer)
        self.oda_client = OdaClient(cfg, signer=signer)
        self.bastion_client = BastionClient(cfg, signer=signer)
        self.logging_management_client = LoggingManagementClient(cfg, signer=signer)
        self.functions_management_client = FunctionsManagementClient(cfg, signer=signer)
        self.resource_manager_client = ResourceManagerClient(cfg, signer=signer)
        self.devops_client = DevopsClient(cfg, signer=signer)
        self.object_storage_client = ObjectStorageClient(cfg, signer=signer)
        self.identity_client = IdentityClient(cfg, signer=signer)   
