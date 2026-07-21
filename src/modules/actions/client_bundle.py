from copy import deepcopy
from oci.analytics import AnalyticsClient
from oci.apigateway import DeploymentClient, GatewayClient
from oci.artifacts import ArtifactsClient
from oci.autoscaling import AutoScalingClient
from oci.bastion import BastionClient
from oci.certificates_management import CertificatesManagementClient
from oci.container_instances import ContainerInstanceClient
from oci.core import BlockstorageClient, ComputeClient, VirtualNetworkClient, ComputeManagementClient
from oci.database import DatabaseClient
from oci.data_integration import DataIntegrationClient
from oci.data_catalog import DataCatalogClient
from oci.data_safe import DataSafeClient
from oci.data_science import DataScienceClient
from oci.devops import DevopsClient
from oci.events import EventsClient
from oci.email import EmailClient
from oci.file_storage import FileStorageClient
from oci.functions import FunctionsManagementClient
from oci.golden_gate import GoldenGateClient
from oci.identity import IdentityClient
from oci.integration import IntegrationInstanceClient
from oci.logging import LoggingManagementClient
from oci.monitoring import MonitoringClient
from oci.network_firewall import NetworkFirewallClient
from oci.network_load_balancer import NetworkLoadBalancerClient
from oci.nosql import NosqlClient
from oci.object_storage import ObjectStorageClient
from oci.oce import OceInstanceClient
from oci.oda import OdaClient
from oci.ons import NotificationControlPlaneClient, NotificationDataPlaneClient
from oci.resource_manager import ResourceManagerClient
from oci.sch import ServiceConnectorClient
from oci.streaming import StreamAdminClient
from oci.vault import VaultsClient
from oci.waas import WaasClient
from oci.waf import WafClient


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
        self.gateway_client = GatewayClient(cfg, signer=signer)
        self.api_deployment_client = DeploymentClient(cfg, signer=signer)
        self.autoscaling_client = AutoScalingClient(cfg, signer=signer)
        self.stream_admin_client = StreamAdminClient(cfg, signer=signer)
        self.data_catalog_client = DataCatalogClient(cfg, signer=signer)
        self.data_safe_client = DataSafeClient(cfg, signer=signer)
        self.data_science_client = DataScienceClient(cfg, signer=signer)
        self.data_integration_client = DataIntegrationClient(cfg, signer=signer)
        self.nosql_client = NosqlClient(cfg, signer=signer)
        self.oce_instance_client = OceInstanceClient(cfg, signer=signer)
        self.vaults_client = VaultsClient(cfg, signer=signer)
        self.waas_client = WaasClient(cfg, signer=signer)
        self.artifacts_client = ArtifactsClient(cfg, signer=signer)
        self.certificates_management_client = CertificatesManagementClient(cfg, signer=signer)
        self.network_firewall_client = NetworkFirewallClient(cfg, signer=signer)
        self.network_load_balancer_client = NetworkLoadBalancerClient(cfg, signer=signer)
        self.golden_gate_client = GoldenGateClient(cfg, signer=signer)
        self.container_instance_client = ContainerInstanceClient(cfg, signer=signer)
        self.service_connector_client = ServiceConnectorClient(cfg, signer=signer)
        self.waf_client = WafClient(cfg, signer=signer)
