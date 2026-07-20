import logging
from datetime import timedelta
from http import HTTPStatus
from types import SimpleNamespace

import pytest

from modules.actions.delete.delete import Deleter
from modules.actions.extend.extend import Extender
from modules.actions.result import Result
from modules.actions.types import ActionStrategy, BaseResourceType
from modules.actions.types.bucket import BucketResource
from modules.actions.types.compartment import CompartmentResource
from modules.actions.types.containerimage import ContainerImageResource
from modules.actions.types.database import DatabaseResource
from modules.actions.types.disworkspace import DISWorkspaceResource
from modules.actions.types.log import LogResource
from modules.config import Configuration
from modules.request_chaser import WorkRequestChaser
from modules.web.setup import ServiceContext


@pytest.mark.parametrize(
    "resource_type",
    [
        "DataScienceNotebookSession",
        "DataScienceProject",
        "DhcpOptions",
        "NoSQLTable",
        "OceInstance",
        "VaultSecret",
        "WaasCertificate",
        "WaasPolicy",
    ],
)
def test_requested_resource_types_are_extend_supported(resource_type):
    resource_cls = Extender.get_resource_type(resource_type)

    assert resource_cls is not None
    assert resource_cls.extend_strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Extender.normalize_resource_type(resource_type) in Extender.supported_norm_keys()


def test_email_domain_delete_and_compartment_actions_are_supported():
    email_domain_cls = Deleter.get_resource_type("EmailDomain")
    compartment_delete_cls = Deleter.get_resource_type("Compartment")
    compartment_extend_cls = Extender.get_resource_type("Compartment")

    assert email_domain_cls is not None
    assert email_domain_cls.delete_strategy == ActionStrategy.DELETE_SDK_MOVE
    assert Deleter.get_resource_type("emaildomain") == email_domain_cls
    assert compartment_delete_cls is CompartmentResource
    assert compartment_extend_cls is CompartmentResource
    assert compartment_delete_cls.delete_strategy == ActionStrategy.DELETE_SDK_MOVE
    assert compartment_extend_cls.extend_strategy == ActionStrategy.EXTEND_IDENTITY


@pytest.mark.parametrize(
    "resource_type",
    [
        "Certificate",
        "CertificateAuthority",
        "ContainerRepository",
        "Database",
        "Log",
        "LogGroup",
    ],
)
def test_additional_requested_resource_types_are_supported(resource_type):
    assert Deleter.get_resource_type(resource_type) is not None
    assert Extender.get_resource_type(resource_type) is not None


@pytest.mark.parametrize(
    "resource_type,alias",
    [
        ("NetworkFirewall", "network_firewall"),
        ("NetworkFirewallPolicy", "network_firewall_policy"),
        ("NetworkLoadBalancer", "network_load_balancer"),
    ],
)
def test_network_security_requested_resource_types_are_supported(resource_type, alias):
    delete_cls = Deleter.get_resource_type(resource_type)
    extend_cls = Extender.get_resource_type(resource_type)

    assert delete_cls is not None
    assert extend_cls is not None
    assert delete_cls.delete_strategy == ActionStrategy.DELETE_SDK_MOVE
    assert extend_cls.extend_strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Deleter.get_resource_type(alias) == delete_cls
    assert Extender.get_resource_type(alias) == extend_cls


@pytest.mark.parametrize(
    "resource_type,alias",
    [
        ("GoldenGateDeployment", "golden_gate_deployment"),
        ("GoldenGateConnection", "golden_gate_connection"),
        ("GoldenGateDatabaseRegistration", "golden_gate_database_registration"),
        ("GoldenGateDeploymentBackup", "golden_gate_deployment_backup"),
        ("GoldenGatePipeline", "golden_gate_pipeline"),
    ],
)
def test_golden_gate_requested_resource_types_are_supported(resource_type, alias):
    delete_cls = Deleter.get_resource_type(resource_type)
    extend_cls = Extender.get_resource_type(resource_type)

    assert delete_cls is not None
    assert extend_cls is not None
    assert delete_cls.delete_strategy == ActionStrategy.DELETE_SDK_MOVE
    assert extend_cls.extend_strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Deleter.get_resource_type(alias) == delete_cls
    assert Extender.get_resource_type(alias) == extend_cls


@pytest.mark.parametrize(
    "resource_type,alias,delete_strategy",
    [
        ("ContainerInstance", "container_instance", ActionStrategy.DELETE_SDK_MOVE),
        ("ContainerRepository", "ContainerRepo", ActionStrategy.DELETE_SDK_MOVE),
        ("ContainerImage", "container_image", ActionStrategy.DELETE_FORCE),
    ],
)
def test_container_requested_resource_types_are_supported(
    resource_type,
    alias,
    delete_strategy,
):
    delete_cls = Deleter.get_resource_type(resource_type)
    extend_cls = Extender.get_resource_type(resource_type)

    assert delete_cls is not None
    assert extend_cls is not None
    assert delete_cls.delete_strategy == delete_strategy
    assert extend_cls.extend_strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Deleter.get_resource_type(alias) == delete_cls
    assert Extender.get_resource_type(alias) == extend_cls


@pytest.mark.parametrize(
    "resource_type,alias,delete_strategy",
    [
        ("Drg", "DRG", ActionStrategy.DELETE_SDK_MOVE),
        ("DISWorkspace", "dis_workspace", ActionStrategy.DELETE_FORCE),
        ("ServiceConnector", "service_connector", ActionStrategy.DELETE_SDK_MOVE),
        ("WebAppFirewall", "web_app_firewall", ActionStrategy.DELETE_SDK_MOVE),
    ],
)
def test_integration_network_requested_resource_types_are_supported(
    resource_type,
    alias,
    delete_strategy,
):
    delete_cls = Deleter.get_resource_type(resource_type)
    extend_cls = Extender.get_resource_type(resource_type)

    assert delete_cls is not None
    assert extend_cls is not None
    assert delete_cls.delete_strategy == delete_strategy
    assert extend_cls.extend_strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Deleter.get_resource_type(alias) == delete_cls
    assert Extender.get_resource_type(alias) == extend_cls


def test_user_scoped_oci_calls_default_enabled(monkeypatch):
    monkeypatch.setenv("OCI_MGMT_DASH_IDM_ENDPOINT", "https://idcs.example.com")
    monkeypatch.setenv("OCI_MGMT_DASH_CLIENT_ID", "client")
    monkeypatch.setenv("OCI_MGMT_DASH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OCI_MGMT_DASH_CLEANUP_CMP", "ocid1.compartment.oc1..cleanup")
    monkeypatch.setenv("OCI_MGMT_DASH_TAG_NAMESPACE", "lifecycle")
    monkeypatch.setenv("OCI_MGMT_DASH_TAG_KEY", "owner")
    monkeypatch.setenv("OCI_MGMT_DASH_FILTER_KEY", "expires_on")

    config = Configuration()

    assert config.get_user_scoped_oci_calls() is True


def test_service_context_can_select_user_scoped_request_chaser():
    user_chaser = object()
    ctx = ServiceContext.__new__(ServiceContext)
    ctx.config = SimpleNamespace(get_user_scoped_oci_calls=lambda: True)
    ctx._get_user_scoped_service_bundle = lambda: {
        "search": object(),
        "deleter": object(),
        "extender": object(),
        "request_chaser": user_chaser,
    }

    assert ctx.get_oci_services(request_chaser=True) == {"request_chaser": user_chaser}


def test_service_context_can_select_app_scoped_request_chaser_when_disabled():
    app_chaser = object()
    ctx = ServiceContext.__new__(ServiceContext)
    ctx.config = SimpleNamespace(get_user_scoped_oci_calls=lambda: False)
    ctx.search = object()
    ctx.deleter = object()
    ctx.extender = object()
    ctx.request_chaser = app_chaser
    ctx.logger = logging.getLogger("tests.service_context")
    ctx._request_path = lambda: "/r"

    assert ctx.get_oci_services(request_chaser=True) == {"request_chaser": app_chaser}


def test_service_context_selects_only_requested_oci_services():
    search = object()
    deleter = object()
    ctx = ServiceContext.__new__(ServiceContext)
    ctx.config = SimpleNamespace(get_user_scoped_oci_calls=lambda: True)
    ctx._get_user_scoped_service_bundle = lambda: {
        "search": search,
        "deleter": deleter,
        "extender": object(),
        "request_chaser": object(),
    }

    assert ctx.get_oci_services(search=True, deleter=True) == {
        "search": search,
        "deleter": deleter,
    }


def test_service_context_requires_explicit_oci_service_request():
    ctx = ServiceContext.__new__(ServiceContext)

    with pytest.raises(ValueError, match="At least one OCI service"):
        ctx.get_oci_services()


def test_user_scoped_work_request_chaser_does_not_eagerly_create_regional_signers():
    signer_regions = []

    WorkRequestChaser(
        {"region": "us-ashburn-1", "tenancy": "ocid1.tenancy.oc1..example"},
        signer=object(),
        regions=["us-ashburn-1", "us-phoenix-1"],
        signer_factory=lambda region: signer_regions.append(region) or object(),
        initialize_clients=False,
    )

    assert signer_regions == []


def make_extender(clients=None):
    extender = Extender.__new__(Extender)
    extender.tag_namespace = "lifecycle"
    extender.tag_key = "expires_on"
    extender.extend_period = timedelta(days=30)
    extender.clients = clients or {}
    extender.logger = logging.getLogger("tests.extender")
    return extender


def make_deleter(clients=None):
    deleter = Deleter.__new__(Deleter)
    deleter.quarantine_cmp = "quarantine"
    deleter.clients = clients or {}
    deleter.logger = logging.getLogger("tests.deleter")
    return deleter


class ExtendCustomResource(BaseResourceType):
    resource_type = "CustomExtend"
    extend_strategy = ActionStrategy.EXTEND_IDENTITY

    def extend(self, extender, resource, region, new_value, defined_tags):
        return Result(
            HTTPStatus.ACCEPTED,
            message="custom extend",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": resource["resource_type"],
                "region": region,
                "new_value": new_value,
                "defined_tags": defined_tags,
            },
        )


class ExtendSdkResource(BaseResourceType):
    resource_type = "SdkExtend"
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = "example_client"
    extend_method_name = "update_example"
    extend_identifier_param = "example_id"
    extend_details_param = "update_example_details"
    extend_details_cls = SimpleNamespace


class DeleteCustomResource(BaseResourceType):
    resource_type = "CustomDelete"
    delete_strategy = ActionStrategy.DELETE_FORCE

    def delete(self, deleter, resource, region, target):
        return Result(
            HTTPStatus.ACCEPTED,
            message="custom delete",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": resource["resource_type"],
                "region": region,
                "target": target,
            },
        )


class DeleteBulkResource(BaseResourceType):
    resource_type = "BulkDelete"
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE

    def delete_bulk_resource(self, deleter, resource, region):
        payload = super().delete_bulk_resource(deleter, resource, region)
        payload.metadata = {"region": region, "owned_by": "resource_type"}
        return payload


def test_extender_extend_instantiates_registered_resource_type(monkeypatch):
    extender = make_extender()
    captured = {}

    monkeypatch.setattr(
        Extender,
        "get_resource_type",
        classmethod(lambda cls, resource_type: ExtendCustomResource),
    )

    def fake_extend_resource(resource_type, resource, region, new_value, defined_tags):
        captured["resource_type"] = resource_type
        captured["resource"] = resource
        captured["region"] = region
        captured["new_value"] = new_value
        captured["defined_tags"] = defined_tags
        return Result(HTTPStatus.OK)

    monkeypatch.setattr(extender, "_extend_resource", fake_extend_resource)

    result = extender.extend(
        {
            "identifier": "ocid1.custom.oc1..example",
            "resource_type": "custom_extend",
            "defined_tags": {"existing": {"key": "value"}},
        }
    )

    assert result.status == HTTPStatus.OK
    assert isinstance(captured["resource_type"], ExtendCustomResource)
    assert captured["region"] is None
    assert captured["defined_tags"] == {"existing": {"key": "value"}}


def test_extender_delegates_custom_extend_logic_to_resource_type():
    extender = make_extender(clients={"us-ashburn-1": SimpleNamespace()})

    result = extender._extend_resource(
        ExtendCustomResource(),
        {
            "identifier": "ocid1.custom.oc1.iad.example",
            "resource_type": "alias-value",
            "region": "us-ashburn-1",
        },
        None,
        "2026-08-08",
        {"old": {"tag": "kept"}},
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.message == "custom extend"
    assert result.metadata == {
        "identifier": "ocid1.custom.oc1.iad.example",
        "resource_type": "CustomExtend",
        "region": "us-ashburn-1",
        "new_value": "2026-08-08",
        "defined_tags": {"old": {"tag": "kept"}},
    }


def test_extender_generic_sdk_tag_strategy_uses_resource_metadata():
    calls = []

    class ExampleClient:
        def update_example(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status=HTTPStatus.OK)

    extender = make_extender(
        clients={"us-ashburn-1": SimpleNamespace(example_client=ExampleClient())}
    )
    defined_tags = {"owner": {"team": "platform"}}

    result = extender._extend_resource(
        ExtendSdkResource(),
        {
            "identifier": "ocid1.sdk.oc1.iad.example",
            "resource_type": "sdk_extend",
            "region": "us-ashburn-1",
        },
        None,
        "2026-08-08",
        defined_tags,
    )

    assert result.status == HTTPStatus.OK
    assert result.metadata == {
        "identifier": "ocid1.sdk.oc1.iad.example",
        "resource_type": "SdkExtend",
        "region": "us-ashburn-1",
        "method": "sdk",
    }
    assert calls == [
        {
            "example_id": "ocid1.sdk.oc1.iad.example",
            "update_example_details": SimpleNamespace(
                defined_tags={
                    "owner": {"team": "platform"},
                    "lifecycle": {"expires_on": "2026-08-08"},
                }
            ),
        }
    ]
    assert defined_tags == {"owner": {"team": "platform"}}


def test_deleter_delegates_custom_delete_logic_to_resource_type():
    deleter = make_deleter()

    result = deleter._delete_resource(
        DeleteCustomResource(),
        {
            "identifier": "ocid1.custom.oc1..example",
            "resource_type": "alias-value",
        },
        "us-phoenix-1",
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.message == "custom delete"
    assert result.metadata == {
        "identifier": "ocid1.custom.oc1..example",
        "resource_type": "CustomDelete",
        "region": "us-phoenix-1",
        "target": "target-compartment",
    }


def test_email_domain_delete_moves_to_target_compartment():
    captured = {}

    class EmailClient:
        def change_email_domain_compartment(self, email_domain_id, details):
            captured["email_domain_id"] = email_domain_id
            captured["details"] = details
            return SimpleNamespace(status=HTTPStatus.ACCEPTED)

    deleter = make_deleter(
        clients={"us-ashburn-1": SimpleNamespace(email_client=EmailClient())}
    )

    result = deleter._delete_single(
        {
            "identifier": "ocid1.emaildomain.oc1.iad.example",
            "resource_type": "EmailDomain",
            "region": "us-ashburn-1",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.metadata["method"] == "sdk"
    assert result.metadata["resource_type"] == "EmailDomain"
    assert captured == {
        "email_domain_id": "ocid1.emaildomain.oc1.iad.example",
        "details": {"compartmentId": "target-compartment"},
    }


def test_compartment_delete_moves_to_target_compartment_in_home_region():
    captured = {}

    class IdentityClient:
        def move_compartment(self, compartment_id, move_compartment_details):
            captured["compartment_id"] = compartment_id
            captured["target_compartment_id"] = (
                move_compartment_details.target_compartment_id
            )
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-compartment"},
            )

    deleter = make_deleter()
    deleter._get_home_region_client_bundle = lambda: (
        "us-ashburn-1",
        SimpleNamespace(identity_client=IdentityClient()),
    )

    result = deleter._delete_single(
        {
            "identifier": "ocid1.compartment.oc1..example",
            "resource_type": "Compartment",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-compartment"
    assert result.metadata == {
        "method": "sdk",
        "resource_type": "Compartment",
        "identifier": "ocid1.compartment.oc1..example",
        "region": "us-ashburn-1",
    }
    assert captured == {
        "compartment_id": "ocid1.compartment.oc1..example",
        "target_compartment_id": "target-compartment",
    }


def test_compartment_extend_updates_tags_in_home_region():
    captured = {}

    class IdentityClient:
        def update_compartment(self, compartment_id, update_compartment_details):
            captured["compartment_id"] = compartment_id
            captured["defined_tags"] = update_compartment_details.defined_tags
            captured["freeform_tags"] = update_compartment_details.freeform_tags
            return SimpleNamespace(status=HTTPStatus.OK)

    extender = make_extender(clients={"us-ashburn-1": SimpleNamespace()})
    extender._get_tenancy_home_region_name = lambda: "us-ashburn-1"
    extender._get_home_region_client_bundle = lambda: (
        "us-ashburn-1",
        SimpleNamespace(identity_client=IdentityClient()),
    )
    defined_tags = {"owner": {"team": "platform"}}

    result = extender._extend_resource(
        CompartmentResource(),
        {
            "identifier": "ocid1.compartment.oc1..example",
            "resource_type": "Compartment",
            "freeform_tags": {"env": "dev"},
        },
        None,
        "2026-08-08",
        defined_tags,
    )

    assert result.status == HTTPStatus.OK
    assert result.metadata == {
        "identifier": "ocid1.compartment.oc1..example",
        "resource_type": "Compartment",
        "region": "us-ashburn-1",
        "method": "identity",
    }
    assert captured == {
        "compartment_id": "ocid1.compartment.oc1..example",
        "defined_tags": {
            "owner": {"team": "platform"},
            "lifecycle": {"expires_on": "2026-08-08"},
        },
        "freeform_tags": {"env": "dev"},
    }
    assert defined_tags == {"owner": {"team": "platform"}}


def test_database_force_delete_calls_database_delete_api():
    captured = {}

    class DatabaseClient:
        def delete_database(self, database_id):
            captured["database_id"] = database_id
            return SimpleNamespace(status=HTTPStatus.ACCEPTED)

    deleter = make_deleter(
        clients={"us-ashburn-1": SimpleNamespace(database_client=DatabaseClient())}
    )

    result = deleter._delete_resource(
        DatabaseResource(),
        {
            "identifier": "ocid1.database.oc1.iad.example",
            "resource_type": "Database",
            "region": "us-ashburn-1",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.metadata == {
        "method": "force",
        "resource_type": "Database",
        "identifier": "ocid1.database.oc1.iad.example",
        "region": "us-ashburn-1",
    }
    assert captured == {"database_id": "ocid1.database.oc1.iad.example"}


def test_container_image_force_delete_calls_artifacts_delete_api():
    captured = {}

    class ArtifactsClient:
        def delete_container_image(self, image_id):
            captured["image_id"] = image_id
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-image"},
            )

    deleter = make_deleter(
        clients={"us-ashburn-1": SimpleNamespace(artifacts_client=ArtifactsClient())}
    )

    result = deleter._delete_resource(
        ContainerImageResource(),
        {
            "identifier": "ocid1.containerimage.oc1.iad.example",
            "resource_type": "ContainerImage",
            "region": "us-ashburn-1",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-image"
    assert result.metadata == {
        "method": "force",
        "resource_type": "ContainerImage",
        "identifier": "ocid1.containerimage.oc1.iad.example",
        "region": "us-ashburn-1",
    }
    assert captured == {"image_id": "ocid1.containerimage.oc1.iad.example"}


def test_dis_workspace_force_delete_calls_data_integration_delete_api():
    captured = {}

    class DataIntegrationClient:
        def delete_workspace(self, workspace_id):
            captured["workspace_id"] = workspace_id
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-dis-workspace"},
            )

    deleter = make_deleter(
        clients={
            "us-ashburn-1": SimpleNamespace(
                data_integration_client=DataIntegrationClient(),
            )
        }
    )

    result = deleter._delete_resource(
        DISWorkspaceResource(),
        {
            "identifier": "ocid1.disworkspace.oc1.iad.example",
            "resource_type": "DISWorkspace",
            "region": "us-ashburn-1",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-dis-workspace"
    assert result.metadata == {
        "method": "force",
        "resource_type": "DISWorkspace",
        "identifier": "ocid1.disworkspace.oc1.iad.example",
        "region": "us-ashburn-1",
    }
    assert captured == {"workspace_id": "ocid1.disworkspace.oc1.iad.example"}


def test_log_force_delete_uses_log_group_id_from_additional_details():
    captured = {}

    class LoggingManagementClient:
        def delete_log(self, log_group_id, log_id):
            captured["log_group_id"] = log_group_id
            captured["log_id"] = log_id
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-log"},
            )

    deleter = make_deleter(
        clients={
            "us-ashburn-1": SimpleNamespace(
                logging_management_client=LoggingManagementClient(),
            )
        }
    )

    result = deleter._delete_resource(
        LogResource(),
        {
            "identifier": "ocid1.log.oc1.iad.example",
            "resource_type": "Log",
            "region": "us-ashburn-1",
            "additional_details": {"logGroupId": "ocid1.loggroup.oc1.iad.example"},
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-log"
    assert result.metadata == {
        "method": "force",
        "resource_type": "Log",
        "identifier": "ocid1.log.oc1.iad.example",
        "region": "us-ashburn-1",
        "log_group_id": "ocid1.loggroup.oc1.iad.example",
    }
    assert captured == {
        "log_group_id": "ocid1.loggroup.oc1.iad.example",
        "log_id": "ocid1.log.oc1.iad.example",
    }


def test_log_extend_updates_tags_with_log_group_id():
    captured = {}

    class LoggingManagementClient:
        def update_log(self, log_group_id, log_id, update_log_details):
            captured["log_group_id"] = log_group_id
            captured["log_id"] = log_id
            captured["defined_tags"] = update_log_details.defined_tags
            captured["freeform_tags"] = update_log_details.freeform_tags
            return SimpleNamespace(status=HTTPStatus.OK)

    extender = make_extender(
        clients={
            "us-ashburn-1": SimpleNamespace(
                logging_management_client=LoggingManagementClient(),
            )
        }
    )
    defined_tags = {"owner": {"team": "platform"}}

    result = extender._extend_resource(
        LogResource(),
        {
            "identifier": "ocid1.log.oc1.iad.example",
            "resource_type": "Log",
            "region": "us-ashburn-1",
            "log_group_id": "ocid1.loggroup.oc1.iad.example",
            "freeformTags": {"env": "prod"},
        },
        None,
        "2026-08-08",
        defined_tags,
    )

    assert result.status == HTTPStatus.OK
    assert result.metadata == {
        "identifier": "ocid1.log.oc1.iad.example",
        "resource_type": "Log",
        "region": "us-ashburn-1",
        "method": "sdk",
        "log_group_id": "ocid1.loggroup.oc1.iad.example",
    }
    assert captured == {
        "log_group_id": "ocid1.loggroup.oc1.iad.example",
        "log_id": "ocid1.log.oc1.iad.example",
        "defined_tags": {
            "owner": {"team": "platform"},
            "lifecycle": {"expires_on": "2026-08-08"},
        },
        "freeform_tags": {"env": "prod"},
    }
    assert defined_tags == {"owner": {"team": "platform"}}


def test_deleter_bulk_strategy_uses_resource_type_payload():
    captured = {}

    class IdentityClient:
        def bulk_move_resources(self, compartment_id, details):
            captured["compartment_id"] = compartment_id
            captured["details"] = details
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-123"},
            )

    deleter = make_deleter(clients={"us-ashburn-1": SimpleNamespace()})
    deleter._get_home_region_client_bundle = lambda: (
        "us-ashburn-1",
        SimpleNamespace(identity_client=IdentityClient()),
    )

    result = deleter._delete_resource(
        DeleteBulkResource(),
        {
            "identifier": "ocid1.bulk.oc1.iad.example",
            "resource_type": "alias-value",
            "region": "us-ashburn-1",
            "compartment_id": "source-compartment",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-123"
    assert result.metadata["method"] == "bulk"
    assert result.metadata["resource_type"] == "BulkDelete"
    assert captured["compartment_id"] == "source-compartment"
    assert captured["details"].target_compartment_id == "target-compartment"
    bulk_resource = captured["details"].resources[0]
    assert bulk_resource.entity_type == "BulkDelete"
    assert bulk_resource.identifier == "ocid1.bulk.oc1.iad.example"
    assert bulk_resource.metadata == {
        "region": "us-ashburn-1",
        "owned_by": "resource_type",
    }


def test_bucket_bulk_resource_uses_required_metadata_only():
    class ObjectStorageClient:
        def get_namespace(self):
            return SimpleNamespace(data="example_namespace")

    deleter = make_deleter(
        clients={
            "us-phoenix-1": SimpleNamespace(
                object_storage_client=ObjectStorageClient()
            )
        }
    )

    payload = BucketResource().delete_bulk_resource(
        deleter,
        {
            "identifier": "ocid1.bucket.oc1.phx.example",
            "resource_type": "Bucket",
            "display_name": "logs-bucket",
        },
        "us-phoenix-1",
    )

    assert payload.entity_type == "bucket"
    assert payload.identifier == "ocid1.bucket.oc1.phx.example"
    assert payload.metadata == {
        "namespaceName": "example_namespace",
        "bucketName": "logs-bucket",
    }


def test_bucket_bulk_move_uses_home_region_identity_client_with_bucket_payload():
    captured = {}

    class ObjectStorageClient:
        def get_namespace(self):
            return SimpleNamespace(data="example_namespace")

    class IdentityClient:
        def bulk_move_resources(self, compartment_id, details):
            captured["compartment_id"] = compartment_id
            captured["details"] = details
            return SimpleNamespace(
                status=HTTPStatus.ACCEPTED,
                headers={"opc-work-request-id": "wr-bucket"},
            )

    deleter = make_deleter(
        clients={
            "us-chicago-1": SimpleNamespace(
                object_storage_client=ObjectStorageClient(),
            )
        }
    )
    deleter._get_home_region_client_bundle = lambda: (
        "us-ashburn-1",
        SimpleNamespace(identity_client=IdentityClient()),
    )

    result = deleter._delete_resource(
        BucketResource(),
        {
            "identifier": "ocid1.bucket.oc1.us-chicago-1.example",
            "resource_type": "Bucket",
            "region": "us-chicago-1",
            "compartment_id": "source-compartment",
            "display_name": "logs-bucket",
        },
        None,
        "target-compartment",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-bucket"
    assert result.metadata["region"] == "us-chicago-1"
    assert result.metadata["action_region"] == "us-ashburn-1"
    assert captured["compartment_id"] == "source-compartment"
    bulk_resource = captured["details"].resources[0]
    assert bulk_resource.entity_type == "bucket"
    assert bulk_resource.identifier == "ocid1.bucket.oc1.us-chicago-1.example"
    assert bulk_resource.metadata == {
        "namespaceName": "example_namespace",
        "bucketName": "logs-bucket",
    }


def test_deleter_bulk_rejection_logs_warning(caplog):
    class RejectedByOci(Exception):
        status = HTTPStatus.BAD_REQUEST
        message = "region is required for bucket bulk move"

    class IdentityClient:
        def bulk_move_resources(self, compartment_id, details):
            raise RejectedByOci()

    deleter = make_deleter(clients={"us-phoenix-1": SimpleNamespace()})
    deleter._get_home_region_client_bundle = lambda: (
        "us-ashburn-1",
        SimpleNamespace(identity_client=IdentityClient()),
    )

    with caplog.at_level(logging.WARNING, logger="tests.deleter"):
        result, success = deleter._delete_bulk_move(
            DeleteBulkResource(),
            {
                "identifier": "ocid1.bulk.oc1.phx.example",
                "resource_type": "BulkDelete",
                "compartment_id": "source-compartment",
            },
            "us-phoenix-1",
            "target-compartment",
        )

    assert success is False
    assert result.status == HTTPStatus.BAD_REQUEST
    assert "Bulk move rejected by OCI" in caplog.text
