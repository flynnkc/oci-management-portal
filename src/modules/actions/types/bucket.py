#!/usr/bin/python3.11
from oci.object_storage.models import UpdateBucketDetails

from .base import ActionStrategy, BaseResourceType


class BucketResource(BaseResourceType):
    resource_type = 'Bucket'
    aliases = ('bucket',)
    delete_bulk_entity_type = 'bucket'
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_SDK_TAG

    def delete_bulk_resource(self, deleter, resource, region) -> dict:
        ocid = resource["identifier"]
        namespace = (
            resource.get("namespace")
            or resource.get("namespace_name")
            or deleter.clients[region].object_storage_client.get_namespace().data
        )
        bucket_name = (
            resource.get("identifier_name")
            or resource.get("display_name")
            or resource.get("bucket_name")
        )
        if not bucket_name:
            raise ValueError(f"Bucket name missing for {ocid}")

        deleter.logger.info(
            "Bulk bucket payload -> ocid=%s name=%s namespace=%s region=%s",
            ocid,
            bucket_name,
            namespace,
            region,
        )
        bulk_resource = super().delete_bulk_resource(deleter, resource, region)
        bulk_resource.metadata = {
            "namespaceName": namespace,
            "bucketName": bucket_name,
        }
        return bulk_resource

    def extend_sdk_tag(self, extender, resource, region, new_value, defined_tags):
        namespace = extender.clients[region].object_storage_client.get_namespace().data
        name = resource.get("display_name") or resource.get("identifier_name")
        return extender.clients[region].object_storage_client.update_bucket(
            namespace,
            name,
            UpdateBucketDetails(
                defined_tags=self._merge_tags(extender, defined_tags, new_value)
            ),
        )
