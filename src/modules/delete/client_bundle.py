from copy import deepcopy
from oci.analytics import AnalyticsClient
from oci.bastion import BastionClient
from oci.core import BlockstorageClient, ComputeClient, VirtualNetworkClient, ComputeManagementClient
from oci.database import DatabaseClient
from oci.file_storage import FileStorageClient
from oci.functions import FunctionsManagementClient
#from oci.os_management_hub import ManagedInstanceGroupClient, ScheduledJobClient, SoftwareSourceClient
from oci.monitoring import MonitoringClient
from oci.events import EventsClient
from oci.email import EmailClient
from oci.ons import NotificationControlPlaneClient, NotificationDataPlaneClient
from oci.integration import IntegrationInstanceClient
#from oci.vault import VaultsClient
#from oci.key_management import KmsVaultClient, KmsManagementClient
from oci.logging import LoggingManagementClient
from oci.oda import OdaClient
from oci.object_storage import ObjectStorageClient
from oci.resource_manager import ResourceManagerClient
from oci.devops import DevopsClient
from oci.identity import IdentityClient

class ClientBundle:
    def __init__(self, config, signer):
        cfg = deepcopy(config)
        self.compute_client = ComputeClient(cfg, signer=signer)
        self.blockstorage_client = BlockstorageClient(cfg, signer=signer)
        self.virtual_network_client = VirtualNetworkClient(cfg, signer=signer)
        self.compute_management_client = ComputeManagementClient(cfg, signer=signer)
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
        self.events_client = EventsClient(cfg, signer=signer)
        self.monitoring_client = MonitoringClient(cfg, signer=signer)
        self.file_storage_client = FileStorageClient(cfg, signer=signer)
        self.email_client = EmailClient(cfg, signer=signer)
        self.notification_control_plane_client= NotificationControlPlaneClient(cfg, signer=signer)
        self.notification_data_plane_client= NotificationDataPlaneClient(cfg, signer=signer)
       # self.vaults_client = VaultsClient(cfg, signer=signer)
       # self.kms_vault_client = KmsVaultClient(cfg, signer=signer)
       # self.kms_management_client = KmsManagementClient(cfg, signer=signer)
        #self.managed_instance_group_client = ManagedInstanceGroupClient(cfg, signer=signer)
        #self.scheduled_job_client = ScheduledJobClient(cfg, signer=signer)
        #self.software_source_client = SoftwareSourceClient(cfg, signer=signer)