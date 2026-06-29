from __future__ import annotations


class MappingError(Exception):
    """Base error for governed mapping failures."""


class SnapshotNotFoundError(MappingError):
    """Raised when a required approved snapshot does not exist."""


class SnapshotImmutableError(MappingError):
    """Raised when a caller attempts to mutate an approved snapshot."""


class LookupDeltaCRError(MappingError):
    """Raised when an unmapped lookup value triggers a governed delta change request."""

    def __init__(
        self,
        *,
        change_request_id: str,
        unmapped_value: str,
        lookup_name: str,
        run_id: str,
    ) -> None:
        super().__init__(
            f"Unmapped lookup value {unmapped_value!r} for {lookup_name!r}; "
            f"LookupDeltaCR {change_request_id} opened for run {run_id}."
        )
        self.change_request_id = change_request_id
        self.unmapped_value = unmapped_value
        self.lookup_name = lookup_name
        self.run_id = run_id


class UnmappedLookupValueError(MappingError):
    """Raised when a source value is absent from an approved lookup snapshot."""

    def __init__(self, *, unmapped_value: str, lookup_name: str) -> None:
        super().__init__(f"Unmapped lookup value {unmapped_value!r} for {lookup_name!r}.")
        self.unmapped_value = unmapped_value
        self.lookup_name = lookup_name
