from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="declared")
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    soft_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    password_resets: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")


class ProjectDefinition(Base):
    __tablename__ = "project_definitions"

    definition_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    repos: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    workspace: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    project_resources: Mapped[str | None] = mapped_column(Text)
    execution_environments: Mapped[list[str] | None] = mapped_column(JSON)
    model_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    canonical_terms: Mapped[list[str] | None] = mapped_column(JSON)
    constraints: Mapped[list[str] | None] = mapped_column(JSON)
    unresolved_questions: Mapped[list[str] | None] = mapped_column(JSON)
    assumptions: Mapped[list[str] | None] = mapped_column(JSON)
    domain_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    codegen_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectRegistry(Base):
    __tablename__ = "project_registry"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_definitions.definition_id"), nullable=False, unique=True
    )
    pm_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=True, index=True
    )
    lexicon_scope: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    soft_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectMembership(Base):
    __tablename__ = "project_memberships"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    token_identifier: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    principal_kind: Mapped[str | None] = mapped_column(String(32))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    reset_token_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_email: Mapped[str | None] = mapped_column(String(320))

    user: Mapped[User] = relationship(back_populates="password_resets")


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    change_request_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    change_request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    approval_record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    change_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("change_requests.change_request_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False)
    approver_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    approval_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RunRecord(Base):
    __tablename__ = "run_records"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False)
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_definition_reference: Mapped[str | None] = mapped_column(String(36))
    source_slice_version: Mapped[str | None] = mapped_column(String(36))
    mapping_snapshot_version: Mapped[str | None] = mapped_column(String(36))
    lookup_snapshot_version: Mapped[str | None] = mapped_column(String(36))
    lookup_snapshot_versions: Mapped[dict[str, str] | None] = mapped_column(JSON)
    code_generation_input_snapshot_version: Mapped[str | None] = mapped_column(String(36))
    codegen_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("code_generation_artifacts.codegen_artifact_id")
    )
    knowledge_freeze_version: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    current_stage: Mapped[str | None] = mapped_column(String(64))
    approvals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    environment: Mapped[str | None] = mapped_column(String(64))
    start_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    pause_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resume_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    completion_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RunCheckpoint(Base):
    __tablename__ = "run_checkpoints"

    run_checkpoint_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    current_stage: Mapped[str | None] = mapped_column(String(64))
    current_object: Mapped[str | None] = mapped_column(String(255))
    current_environment: Mapped[str | None] = mapped_column(String(64))
    approved_snapshots: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_completed_checkpoint_boundary: Mapped[str | None] = mapped_column(String(255))
    pause_reason: Mapped[str | None] = mapped_column(Text)
    checkpoint_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Feed(Base):
    __tablename__ = "source_definitions"

    source_definition_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    access_reference: Mapped[str | None] = mapped_column(String(255))
    selection_information: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    layout_information: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    destination_object_references: Mapped[list[str] | None] = mapped_column(JSON)
    sample_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    copybook_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    mapping_hints: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformation_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FeedSlice(Base):
    __tablename__ = "source_slices"

    source_slice_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_artifact: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    masking_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    header_csv: Mapped[str | None] = mapped_column(Text)
    slice_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_approval")
    approval_rejection_reason: Mapped[str | None] = mapped_column(Text)
    parse_warnings: Mapped[list[str] | None] = mapped_column(JSON)
    data_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    file_storage_path: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FeedSliceRow(Base):
    __tablename__ = "source_slice_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_slice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_slices.source_slice_id"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row_csv: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FeedComment(Base):
    __tablename__ = "feed_comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feed_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_slice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_slices.source_slice_id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# Backward-compatible aliases while the rename propagates through tests and docs.
SourceDefinition = Feed
SourceContract = Feed
SourceSlice = FeedSlice
SourceSliceRow = FeedSliceRow


class SourceSchemaArtifact(Base):
    __tablename__ = "source_schema_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "source_definition_id",
            "source_slice_version",
            name="uq_source_schema_artifacts_definition_version",
        ),
    )

    schema_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    destination_ddl: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceValueSummary(Base):
    __tablename__ = "source_value_summaries"
    __table_args__ = (
        UniqueConstraint(
            "source_definition_id",
            "source_slice_version",
            "field_name",
            name="uq_source_value_summaries_definition_version_field",
        ),
    )

    summary_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MappingSnapshot(Base):
    __tablename__ = "mapping_snapshots"

    mapping_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False
    )
    source_definition_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=True
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_bindings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    destination_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    destination_columns: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    current_ball_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupSnapshot(Base):
    __tablename__ = "lookup_snapshots"

    lookup_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    lookup_snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    value_map: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupValueMap(Base):
    __tablename__ = "lookup_value_maps"

    lookup_value_map_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_table: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    source_value_map: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    destination_mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    unmapped_source_values: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectFiber(Base):
    __tablename__ = "project_fibers"

    fiber_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feed_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    fiber_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fiber_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    proposed_mappings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    field_bindings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    output_sql: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MappingArtifact(Base):
    __tablename__ = "mapping_artifacts"

    mapping_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lookup_snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mapped_rows: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=False, index=True
    )
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    row_count_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReconciliationLineageRow(Base):
    __tablename__ = "reconciliation_lineage_rows"

    lineage_row_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_reports.report_id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=False, index=True
    )
    source_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_row_key: Mapped[str | None] = mapped_column(String(255))
    destination_row_id: Mapped[str | None] = mapped_column(String(255))
    mapping_rules_applied: Mapped[list[str] | None] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_detail: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DryRunArtifact(Base):
    __tablename__ = "dry_run_artifacts"

    dry_run_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    field_coverage_pct: Mapped[float | None] = mapped_column(Float)
    pii_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sample_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    failures: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    push_back_comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectSchemaAnalysis(Base):
    __tablename__ = "project_schema_analyses"

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_definitions.project_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    destination_object_sequence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    identified_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CodeGenerationArtifact(Base):
    __tablename__ = "code_generation_artifacts"

    codegen_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    source_definition_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=True, index=True
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run_records.run_id"), nullable=True, index=True
    )
    source_slice_version: Mapped[str | None] = mapped_column(String(255))
    mapping_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    lookup_snapshot_version: Mapped[str | None] = mapped_column(String(255))
    sql_bundle: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project_registry.project_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("run_records.run_id"))
    change_request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("change_requests.change_request_id")
    )
    approval_record_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("approval_records.approval_record_id")
    )
    source_definition_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id")
    )
    source_slice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_slices.source_slice_id")
    )
    event_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deep_link: Mapped[str] = mapped_column(String(1024), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class MappingBindingSignOff(Base):
    __tablename__ = "mapping_binding_sign_offs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mapping_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mapping_snapshots.mapping_snapshot_id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_object_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_field: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_field: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "mapping_snapshot_id",
            "destination_object_name",
            "source_field",
            "destination_field",
            "user_id",
            name="uq_mapping_binding_sign_off",
        ),
    )


class LookupSignOff(Base):
    __tablename__ = "lookup_sign_offs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lookup_value_map_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lookup_value_maps.lookup_value_map_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("lookup_value_map_id", "user_id", name="uq_lookup_sign_off"),
    )


class AICallLog(Base):
    __tablename__ = "ai_call_log"

    call_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False, index=True
    )
    feature: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    call_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VersionHistory(Base):
    __tablename__ = "version_history"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_version_history_entity", "entity_type", "entity_id", "field_name"),
    )