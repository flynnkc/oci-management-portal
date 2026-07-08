import logging
from http import HTTPStatus

import pytest

from modules.actions import (
    ActionKind,
    ActionStrategy,
    BaseAction,
    Deleter,
    Extender,
    ResourceActionSpec,
    BaseResourceType,
    Result,
)


class FakeAction(BaseAction):
    ACTION_SPECS = (
        ResourceActionSpec(
            resource_type="Widget",
            action=ActionKind.DELETE,
            strategy=ActionStrategy.DELETE_FORCE,
            aliases=("WidgetLegacy",),
        ),
    )


class FakeSigner:
    def __init__(self, region):
        self.region = region


class FakeBulkResource(BaseResourceType):
    resource_type = "Bucket"
    aliases = ("bucket",)
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE


class FakeSdkMoveResource(BaseResourceType):
    resource_type = "LogGroup"
    delete_strategy = ActionStrategy.DELETE_SDK_MOVE
    delete_client_attr = "logging_management_client"
    delete_method_name = "change_log_group_compartment"


class FakeDeleteResponse:
    status = HTTPStatus.ACCEPTED
    headers = {"opc-work-request-id": "wr-123"}


class FakeDeleteAction:
    def __init__(self):
        self.clients = {"us-ashburn-1": object()}
        self.logger = logging.getLogger(__name__)
        self.bulk_resource = None

    def _try_bulk_one(self, resource, region, target):
        self.bulk_resource = resource
        return Result(HTTPStatus.ACCEPTED, metadata={}), True

    def _move_with_sdk_spec(self, move_spec, identifier, region, target_compartment_id):
        return FakeDeleteResponse()


def test_base_action_derives_supported_keys_from_specs():
    assert "widget" in FakeAction.supported_norm_keys()
    assert "widgetlegacy" in FakeAction.supported_norm_keys()
    assert FakeAction.supported_display_map()["widgetlegacy"] == "Widget"


def test_deleter_specs_include_sdk_move_metadata():
    spec = Deleter.get_action_spec("LogGroup")

    assert Deleter.ACTION_KIND == ActionKind.DELETE
    assert "modules.actions.types" in Deleter.ACTION_SPEC_MODULES
    assert spec is not None
    assert spec.action == ActionKind.DELETE
    assert spec.strategy == ActionStrategy.DELETE_SDK_MOVE
    assert spec.client_attr == "logging_management_client"
    assert spec.method_name == "change_log_group_compartment"


def test_extender_specs_include_expected_strategies():
    assert Extender.ACTION_KIND == ActionKind.EXTEND
    assert "modules.actions.types" in Extender.ACTION_SPEC_MODULES
    assert Extender.get_action_spec("bucket").strategy == ActionStrategy.EXTEND_SDK_TAG
    assert Extender.get_action_spec("Instance").strategy == ActionStrategy.EXTEND_BULK_TAG
    assert Extender.get_action_spec("User").strategy == ActionStrategy.EXTEND_IDENTITY


def test_shared_resource_registration_serves_both_actions():
    assert Deleter.get_action_spec("Instance").strategy == ActionStrategy.DELETE_BULK_MOVE
    assert Extender.get_action_spec("Instance").strategy == ActionStrategy.EXTEND_BULK_TAG


def test_force_delete_keys_are_derived_from_delete_specs():
    force_delete_keys = Deleter.force_delete_norm_keys()

    assert "user" in force_delete_keys
    assert "dynamicresourcegroup" in force_delete_keys
    assert "instance" not in force_delete_keys
    assert force_delete_keys == Deleter.supported_strategy_norm_keys(
        ActionStrategy.DELETE_FORCE
    )


def test_force_delete_is_owned_by_resource_types():
    assert Deleter.get_resource_type("User").force_delete != BaseResourceType.force_delete
    assert (
        Deleter.get_resource_type("DynamicResourceGroup").force_delete
        != BaseResourceType.force_delete
    )


def test_resource_type_classes_are_discovered():
    instance_type = Deleter.get_resource_type("Instance")

    assert issubclass(instance_type, BaseResourceType)
    assert instance_type.resource_type == "Instance"
    assert instance_type.delete_strategy == ActionStrategy.DELETE_BULK_MOVE
    assert instance_type.extend_strategy == ActionStrategy.EXTEND_BULK_TAG


def test_deleter_does_not_expose_legacy_force_delete_registries():
    deleter = Deleter(
        config={"region": "us-ashburn-1"},
        quarantine_cmp="ocid1.compartment.oc1..quarantine",
        signer=FakeSigner("us-ashburn-1"),
        handler=logging.NullHandler(),
        log_level=logging.INFO,
    )

    assert not hasattr(deleter, "force_delete_types")
    assert not hasattr(deleter, "force_delete_handlers")
    assert not hasattr(deleter, "force_delete_user")


def test_base_action_uses_signer_factory_for_regional_signers():
    calls = []

    def signer_factory(region):
        calls.append(region)
        return FakeSigner(region)

    action = FakeAction(
        config={"region": "us-ashburn-1"},
        signer=FakeSigner("us-ashburn-1"),
        signer_factory=signer_factory,
        handler=logging.NullHandler(),
        log_level=logging.INFO,
        regions=["us-ashburn-1", "us-phoenix-1"],
    )

    signer = action._signer_for_region("us-phoenix-1")

    assert signer.region == "us-phoenix-1"
    assert calls == ["us-phoenix-1"]


def test_base_action_rejects_plain_signer_for_other_region():
    signer = FakeSigner("us-ashburn-1")
    action = FakeAction(
        config={"region": "us-ashburn-1"},
        signer=signer,
        handler=logging.NullHandler(),
        log_level=logging.INFO,
    )

    with pytest.raises(ValueError, match="signer_factory is required"):
        action._signer_for_region("us-phoenix-1")

    assert signer.region == "us-ashburn-1"


def test_base_action_requires_factory_for_multiple_regions():
    with pytest.raises(ValueError, match="signer_factory is required"):
        FakeAction(
            config={"region": "us-ashburn-1"},
            signer=FakeSigner("us-ashburn-1"),
            handler=logging.NullHandler(),
            log_level=logging.INFO,
            regions=["us-ashburn-1", "us-phoenix-1"],
        )


def test_delete_canonicalizes_alias_before_strategy_dispatch():
    deleter = FakeDeleteAction()

    result = FakeBulkResource().delete(
        deleter,
        {
            "resource_type": "bucket",
            "identifier": "ocid1.bucket.oc1..example",
            "region": "us-ashburn-1",
        },
        region=None,
        target="ocid1.compartment.oc1..quarantine",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert deleter.bulk_resource["resource_type"] == "Bucket"
    assert result.metadata["resource_type"] == "Bucket"


def test_sdk_move_preserves_work_request_from_raw_response():
    deleter = FakeDeleteAction()

    result = FakeSdkMoveResource().delete(
        deleter,
        {
            "resource_type": "loggroup",
            "identifier": "ocid1.loggroup.oc1..example",
            "region": "us-ashburn-1",
        },
        region=None,
        target="ocid1.compartment.oc1..quarantine",
    )

    assert result.status == HTTPStatus.ACCEPTED
    assert result.work_request == "wr-123"
    assert result.metadata["resource_type"] == "LogGroup"
