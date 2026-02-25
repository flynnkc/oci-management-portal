#!/usr/bin/python3.11

class Result:
    """Standardized return container for delete/extend operations."""

    def __init__(
        self,
        status: int,
        work_request: str | None = None,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.status: int = status
        self.work_request: str | None = work_request
        self.message: str | None = message
        self.metadata: dict = metadata or {}
        self.is_pollable: bool = bool(work_request)

    @property
    def ok(self) -> bool:
        return 200 <= self.status <= 299