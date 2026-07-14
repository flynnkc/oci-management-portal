import logging
from datetime import timedelta
from http import HTTPStatus
from types import SimpleNamespace

from modules.actions.delete.delete import Deleter
from modules.actions.extend.extend import Extender
from modules.actions.result import Result
from modules.actions.types import ActionStrategy, BaseResourceType
from modules.actions.types.bucket import BucketResource


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
        payload["metadata"] = {"region": region, "owned_by": "resource_type"}
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
    assert captured["details"].resources == [
        {
            "entityType": "BulkDelete",
            "identifier": "ocid1.bulk.oc1.iad.example",
            "metadata": {"region": "us-ashburn-1", "owned_by": "resource_type"},
        }
    ]


def test_bucket_bulk_resource_includes_region_metadata():
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

    assert payload == {
        "entityType": "Bucket",
        "identifier": "ocid1.bucket.oc1.phx.example",
        "metadata": {
            "namespaceName": "example_namespace",
            "bucketName": "logs-bucket",
            "region": "us-phoenix-1",
        },
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
