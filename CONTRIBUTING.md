# Contributing to OCI Management Portal

Thanks for helping improve OCI Management Portal. This project is a Flask application for discovering and managing OCI resources with ownership and lifecycle tags, so changes should stay focused, testable, and careful around OCI credentials, tags, and destructive workflows.

## Getting Started

Use Python 3.11 or newer.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt
```

Copy or source `sample.env` for local configuration, then replace sample values with values for your tenancy and Identity Domain.

```bash
source sample.env
```

Do not commit real OCIDs, client secrets, tenancy-specific credentials, private keys, tokens, or generated session/cache data.

## Running Locally

Development server:

```bash
cd src
flask --app wsgi:app run --debug
```

Production-like local server:

```bash
cd src
gunicorn -c gunicorn.config.py wsgi:app
```

Docker:

```bash
docker build -t oci-management-portal:latest .
docker run --rm -p 5000:5000 --env-file sample.env oci-management-portal:latest
```

## Testing

Run the test suite from the repository root:

```bash
pytest
```

Add or update tests when changing action orchestration, resource type behavior, authentication/session handling, search/filter behavior, or anything that affects delete and extend workflows. Prefer mocked OCI clients in tests instead of requiring live OCI access.

## Code Guidelines

- Keep changes scoped to one logical improvement or fix.
- Follow the existing package layout under `src/modules`.
- Keep resource-specific action behavior in the appropriate `src/modules/actions/types/` module when possible.
- Avoid broad refactors in the same pull request as a behavior change.
- Preserve existing environment variable names and defaults unless the change intentionally updates configuration behavior.
- Treat delete, move, and extend operations as high-risk paths: make error handling explicit and keep result metadata useful for troubleshooting.
- Keep templates and static assets consistent with the existing Bootstrap-based UI.

## Adding a Resource Type

Most OCI resource support is declared with a small `BaseResourceType` subclass in `src/modules/actions/types/`. The action layer discovers these classes and uses their metadata to decide how delete and extend operations should run.

For example, to add a resource that needs custom force-delete logic and can be updated through a service SDK call for extend:

```python
from http import HTTPStatus

from oci.example_service.models import UpdateExampleResourceDetails

from modules.actions.result import Result

from .base import ActionStrategy, BaseResourceType


class ExampleResource(BaseResourceType):
    resource_type = "ExampleResource"
    aliases = ("example_resource", "exampleresource")

    delete_strategy = ActionStrategy.DELETE_FORCE

    extend_strategy = ActionStrategy.EXTEND_SDK_TAG
    extend_client_attr = "example_client"
    extend_method_name = "update_example_resource"
    extend_identifier_param = "example_resource_id"
    extend_details_param = "update_example_resource_details"
    extend_details_cls = UpdateExampleResourceDetails

    def force_delete(self, deleter, resource):
        region = self._region(deleter, resource)
        client = deleter.clients[region].example_client
        response = client.delete_example_resource(
            example_resource_id=resource["identifier"]
        )
        return Result(
            response.status or HTTPStatus.ACCEPTED,
            message="Delete requested",
            metadata={
                "identifier": resource["identifier"],
                "resource_type": self.resource_type,
                "region": region,
                "method": "force",
            },
        )
```

Then make sure the module is imported by `src/modules/actions/types/__init__.py` so discovery can register it.

Use the simplest strategy that matches the OCI API:

- `DELETE_BULK_MOVE` when Identity `bulk_move_resources` can move the resource.
- `DELETE_SDK_MOVE` when the service has a `change_*_compartment` style method.
- `DELETE_FORCE` when custom delete logic is required.
- `EXTEND_BULK_TAG` when Identity `bulk_edit_tags` can update the expiry tag.
- `EXTEND_SDK_TAG` when a service-specific update method must write tags.
- `EXTEND_IDENTITY` when identity or domain-specific custom logic is required.

If the common metadata shape is not enough, override `delete_bulk_resource()`, `delete()`, `force_delete()`, or `extend()` in the resource class. Add or update tests under `tests/` with mocked clients so the behavior is validated without live OCI access.

## Documentation

Update documentation when a change affects:

- required or optional environment variables
- local run or deployment steps
- Docker behavior
- session backend behavior
- supported OCI resource types
- user-visible delete, extend, search, or authentication behavior

The main project documentation lives in `README.md`. Resource type implementation notes live in `src/modules/actions/types/README.md`.

## Pull Requests

Before opening a pull request:

1. Rebase or merge the latest main branch.
2. Run `pytest`.
3. Run the app locally if the change affects runtime behavior.
4. Check that no secrets or local-only generated files are included.

In the pull request description, include:

- the problem or use case
- a short implementation summary
- testing and validation notes
- screenshots for UI changes
- related issue numbers, when applicable

Use clear, descriptive commit messages. Small, focused pull requests are easiest to review and safest to merge.

## Reporting Issues

Use GitHub Issues for bugs and feature requests:

<https://github.com/flynnkc/oci-management-portal/issues>

For bugs, include your environment, steps to reproduce, expected behavior, actual behavior, and relevant logs or screenshots. For feature requests, include the use case, expected outcome, and any OCI constraints that matter.
