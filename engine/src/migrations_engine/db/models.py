from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
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
    environment: Mapped[str | None] = mapped_column(String(64))
    execution_environments: Mapped[list[str] | None] = mapped_column(JSON)
    model_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    canonical_terms: Mapped[list[str] | None] = mapped_column(JSON)
    constraints: Mapped[list[str] | None] = mapped_column(JSON)
    unresolved_questions: Mapped[list[str] | None] = mapped_column(JSON)
    assumptions: Mapped[list[str] | None] = mapped_column(JSON)
    domain_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
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
    lexicon_scope: Mapped[dict[str, Any] | None] = mapped_column(JSON)
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
    code_generation_input_snapshot_version: Mapped[str | None] = mapped_column(String(36))
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


class SourceDefinition(Base):
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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceSlice(Base):
    __tablename__ = "source_slices"

    source_slice_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_artifact: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    masking_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    slice_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceValueSummary(Base):
    __tablename__ = "source_value_summaries"
    __table_args__ = (
        UniqueConstraint(
            "source_definition_id",
            "source_slice_version",
            "field_name",
            name="uq_source_value_summaries_definition_slice_field",
        ),
    )

    summary_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    source_slice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LookupValueMap(Base):
    __tablename__ = "lookup_value_maps"
    __table_args__ = (
        UniqueConstraint(
            "source_definition_id",
            "lookup_name",
            "status",
            name="uq_lookup_value_maps_definition_lookup_status",
        ),
    )

    lookup_value_map_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_definitions.source_definition_id"), nullable=False
    )
    lookup_name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_table: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MappingSnapshot(Base):
    __tablename__ = "mapping_snapshots"

    mapping_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_registry.project_id"), nullable=False
    )
    destination_object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    field_bindings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
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
