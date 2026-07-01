from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


PlatformRole = Literal["central_team", "project_stakeholder", "read_only_auditor"]
UserStatus = Literal["active", "disabled"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AuthenticatedUserResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    session_version: int
    user: AuthenticatedUserResponse


class SessionResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus
    expires_at: datetime
    session_version: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetAccepted(BaseModel):
    accepted: bool = True


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None
    role: PlatformRole


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: PlatformRole | None = None
    status: UserStatus | None = None


class ProjectMemberResponse(BaseModel):
    project_id: str
    user_id: str
    created_at: datetime


class MembershipResponse(BaseModel):
    project_id: str
    user_id: str
    warning: str | None = None


TargetDbEngine = Literal["mssql", "oracle", "postgresql", "mysql"]
ProjectStatus = Literal["active", "archived"]


class LatestRunSummary(BaseModel):
    current_stage: str | None
    run_status: str
    source_type: str | None
    stage_entered_at: datetime


class MigrationProjectConfig(BaseModel):
    target_db_engine: TargetDbEngine | None = None
    staging_schema: str | None = None
    dry_run: bool = False
    sample_policy: dict[str, Any] | None = None
    destination_schema_ddl: str | None = None
    environments: list[str] | None = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    goal: str | None
    repos: list[dict[str, Any]] | None
    workspace: dict[str, Any] | None
    environment: str | None
    execution_environments: list[str] | None
    model_policy: dict[str, Any] | None
    canonical_terms: list[str] | None
    constraints: list[str] | None
    unresolved_questions: list[str] | None
    assumptions: list[str] | None
    domain_config: MigrationProjectConfig | None
    lexicon_scope: dict[str, Any] | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    latest_run_summary: LatestRunSummary | None = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str | None = None
    repos: list[dict[str, Any]] | None = None
    workspace: dict[str, Any] | None = None
    environment: str | None = None
    execution_environments: list[str] | None = None
    model_policy: dict[str, Any] | None = None
    canonical_terms: list[str] | None = None
    constraints: list[str] | None = None
    unresolved_questions: list[str] | None = None
    assumptions: list[str] | None = None
    domain_config: MigrationProjectConfig | None = None
    lexicon_scope: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = None
    repos: list[dict[str, Any]] | None = None
    workspace: dict[str, Any] | None = None
    environment: str | None = None
    execution_environments: list[str] | None = None
    model_policy: dict[str, Any] | None = None
    canonical_terms: list[str] | None = None
    constraints: list[str] | None = None
    unresolved_questions: list[str] | None = None
    assumptions: list[str] | None = None
    domain_config: MigrationProjectConfig | None = None
    lexicon_scope: dict[str, Any] | None = None


class FeedCreateRequest(BaseModel):
    source_type: Literal["csv", "fixed_length_file"]
    label: str = Field(min_length=1, max_length=255)
    encoding: str = Field(default="utf-8", max_length=32)


class FeedResponse(BaseModel):
    source_definition_id: str
    project_id: str
    source_type: str
    label: str
    encoding: str
    destination_object_references: list[str] | None
    layout_information: list[dict[str, Any]] | None
    copybook_text: str | None
    status: str
    created_at: datetime


class FeedSliceResponse(BaseModel):
    source_slice_id: str
    source_definition_id: str
    source_slice_version: str
    header_csv: str | None
    row_count: int
    status: str
    approval_rejection_reason: str | None
    parse_warnings: list[str] | None
    preview_rows: list[str]
    created_at: datetime


class FeedSliceApprovalItemResponse(BaseModel):
    project_id: str
    project_name: str
    source_definition_id: str
    source_label: str
    source_type: str
    source_slice_id: str
    source_slice_version: str
    row_count: int
    status: str
    parse_warnings: list[str] | None
    created_at: datetime


class FeedSliceRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class FeedSliceResubmitRequest(BaseModel):
    encoding: str | None = Field(default=None, max_length=32)
    parse_settings: dict[str, Any] | None = None


class FeedSliceApprovalCountResponse(BaseModel):
    pending_count: int


class FiberCreateRequest(BaseModel):
    fiber_type: Literal["lookup", "domain_object"]
    fiber_key: str = Field(min_length=1, max_length=255)
    source: Literal["auto", "manual"] = "manual"


class FiberResponse(BaseModel):
    fiber_id: str
    feed_id: str
    project_id: str
    fiber_type: Literal["lookup", "domain_object"]
    fiber_key: str
    status: str
    source: Literal["auto", "manual"]
    proposed_mappings: list[dict[str, Any]] | None
    field_bindings: list[dict[str, Any]] | None
    output_sql: str | None
    created_at: datetime
    updated_at: datetime


class LookupSourceEntryResponse(BaseModel):
    entry_id: str
    fiber_id: str
    lookup_name: str
    source_value: str
    discovery_type: str
    created_at: datetime


class LookupDestFeedResponse(BaseModel):
    dest_feed_id: str
    fiber_id: str
    lookup_name: str
    columns: list[str]
    created_at: datetime


class LookupDestEntryResponse(BaseModel):
    entry_id: str
    dest_feed_id: str
    row_data: dict[str, Any]
    created_at: datetime


class LookupMappingResponse(BaseModel):
    mapping_id: str
    fiber_id: str
    lookup_name: str
    source_entry_id: str
    source_value: str
    dest_entry_id: str | None
    dest_row: dict[str, Any] | None
    confidence_score: float | None
    status: Literal["proposed", "confirmed", "overridden"]
    mapped_by: Literal["ai", "operator", "business"]
    created_at: datetime
    updated_at: datetime


class SourceAnalysisResponse(BaseModel):
    schema_artifact_id: str
    status: Literal["completed"] = "completed"


class SourceSchemaColumnResponse(BaseModel):
    name: str
    inferred_type: Literal["text", "integer", "decimal", "date", "boolean", "uuid"]
    nullable: bool
    max_length: int | None


class SourceSchemaArtifactResponse(BaseModel):
    schema_artifact_id: str
    source_definition_id: str
    source_slice_version: str
    columns: list[SourceSchemaColumnResponse]
    created_at: datetime


class SourceValueSummaryResponse(BaseModel):
    summary_id: str
    source_definition_id: str
    source_slice_version: str
    field_name: str
    value_counts: dict[str, int]
    created_at: datetime


class CodegenTriggerResponse(BaseModel):
    codegen_artifact_id: str
    project_id: str
    destination_object_name: str
    status: Literal["active", "superseded"]
    sql_bundle_preview: str
    source_slice_version: str | None
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    created_at: datetime


class CodegenArtifactResponse(BaseModel):
    codegen_artifact_id: str
    project_id: str
    destination_object_name: str
    run_id: str | None
    source_slice_version: str | None
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    sql_bundle: str | None
    status: Literal["active", "superseded"]
    created_at: datetime
    superseded_at: datetime | None


class DeliveryBundleResponse(BaseModel):
    filename: str
    sql_bundle: str
    artifact_count: int


class LookupValueMapCreateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)
    destination_table: list[dict[str, Any]]
    source_value_map: dict[str, str] = Field(default_factory=dict)


class LookupValueMapResponse(BaseModel):
    lookup_value_map_id: str
    source_definition_id: str
    lookup_name: str
    destination_table: list[dict[str, Any]]
    source_value_map: dict[str, str]
    status: Literal["draft", "approved"]
    created_at: datetime


class LookupSnapshotGenerateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)


class LookupSnapshotResponse(BaseModel):
    lookup_snapshot_id: str
    project_id: str
    lookup_name: str
    lookup_snapshot_version: str
    value_map: dict[str, str]
    status: Literal["draft", "approved"]
    approved_at: datetime | None
    approved_by_user_id: str | None
    created_at: datetime


class MappingFieldBindingResponse(BaseModel):
    source_field: str
    destination_field: str
    lookup_name: str | None


class MappingSnapshotResponse(BaseModel):
    mapping_snapshot_id: str
    project_id: str
    destination_object_name: str
    mapping_snapshot_version: str
    field_bindings: list[MappingFieldBindingResponse]
    status: str
    approved_at: datetime | None
    approved_by_user_id: str | None
    created_at: datetime


class MappingPatchRequest(BaseModel):
    field_bindings: list[MappingFieldBindingResponse]


class MappingReviewResponse(MappingSnapshotResponse):
    destination_fields: list[str]


class MappingRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class GateApproveRequest(BaseModel):
    notes: str | None = None


class GatePushbackRequest(BaseModel):
    affected_objects: list[str]
    required_changes: str = Field(min_length=1, max_length=1000)
    notes: str | None = None


class GateRecordResponse(BaseModel):
    gate: str
    decision: str
    approver_user_id: str | None
    decided_at: datetime
    notes: str | None
    affected_objects: list[str] | None = None
    required_changes: str | None = None


class GateStatusResponse(BaseModel):
    run_id: str
    gate_1: GateRecordResponse | None
    gate_2: GateRecordResponse | None


class FieldBindingSummary(BaseModel):
    source_field: str
    destination_field: str
    lookup_name: str | None


class Gate1EvidenceResponse(BaseModel):
    run_id: str
    destination_object_name: str
    mapping_snapshot_version: str | None
    field_bindings: list[FieldBindingSummary]
    pii_fields: list[str]
    coverage_gaps: list[str]


class LookupRowResponse(BaseModel):
    source_value: str
    destination_value: str | None
    state: str


class Gate2EvidenceResponse(BaseModel):
    run_id: str
    lookup_name: str
    rows: list[LookupRowResponse]
    confirmed_count: int
    unmapped_count: int


class RunCreateRequest(BaseModel):
    destination_object_name: str = Field(min_length=1, max_length=255)
    source_definition_id: str
    environment: str | None = None


class RunResponse(BaseModel):
    run_id: str
    project_id: str
    destination_object_name: str
    source_definition_reference: str | None
    environment: str | None
    status: str
    current_stage: str | None
    source_slice_version: str | None
    mapping_snapshot_version: str | None
    lookup_snapshot_version: str | None
    lookup_snapshot_versions: dict[str, str] | None
    code_generation_input_snapshot_version: str | None
    codegen_artifact_id: str | None
    knowledge_freeze_version: str | None
    start_metadata: dict[str, Any] | None
    pause_metadata: dict[str, Any] | None
    resume_metadata: dict[str, Any] | None
    completion_metadata: dict[str, Any] | None
    started_at: datetime | None
    last_checkpoint_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunCheckpointResponse(BaseModel):
    run_checkpoint_id: str
    run_id: str
    current_stage: str | None
    current_object: str | None
    current_environment: str | None
    approved_snapshots: dict[str, Any] | None
    last_completed_checkpoint_boundary: str | None
    last_completed_row: int | None
    pause_reason: str | None
    created_at: datetime


class ReconciliationCheckResult(BaseModel):
    check_name: str
    status: Literal["pass", "fail"]
    detail: str


class RowCountSummary(BaseModel):
    source_rows: int
    destination_rows: int
    rejected: int
    duplicated: int
    partially_mapped: int


class ReconciliationReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    run_id: str
    checks: list[ReconciliationCheckResult]
    overall_status: Literal["in_progress", "pass", "fail"]
    row_count_summary: RowCountSummary | None
    created_at: datetime
    completed_at: datetime | None


class LineageRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lineage_row_id: str
    source_row_index: int | None
    source_row_key: str | None
    destination_row_id: str | None
    mapping_rules_applied: list[str] | None
    outcome: Literal["confirmed", "rejected", "duplicated", "partially_mapped"]
    outcome_detail: str | None


class LineageResponse(BaseModel):
    rows: list[LineageRowResponse]
    total: int
    offset: int
    limit: int


class ReconciliationExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    run_id: str
    exported_at: datetime
    checks: list[ReconciliationCheckResult]
    overall_status: Literal["in_progress", "pass", "fail"]
    row_count_summary: RowCountSummary | None
    lineage_rows: list[LineageRowResponse]
