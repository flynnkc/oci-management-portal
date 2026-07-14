# Resource Type Plugins

Resource support is declared through one module per resource type. Each module should
define a `BaseResourceType` subclass:

```python
from .base import ActionStrategy, BaseResourceType


class InstanceResource(BaseResourceType):
    resource_type = "Instance"
    delete_strategy = ActionStrategy.DELETE_BULK_MOVE
    extend_strategy = ActionStrategy.EXTEND_BULK_TAG
```

`Deleter` and `Extender` load this package through `ACTION_SPEC_MODULES`, discover
`BaseResourceType` subclasses, filter them by `ACTION_KIND`, and derive supported
resource lists from those classes.

Set `aliases` for casing or naming variants, such as `Bucket` and `bucket`.
Most resource classes only need metadata. Override `delete()` or `extend()` when a
resource needs custom handling beyond the default strategy behavior. Override
`force_delete()` for resources using `ActionStrategy.DELETE_FORCE`.
