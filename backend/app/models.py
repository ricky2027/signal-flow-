from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    String,
    DateTime,
    Integer,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_result_value(self, value, dialect):
        return (
            value.replace(tzinfo=timezone.utc)
            if value and value.tzinfo is None
            else value
        )


J = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)


class Session(Base, Identified):
    __tablename__ = "demo_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Prospect(Base, Identified):
    __tablename__ = "prospects"
    session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id"), index=True)
    data: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class Run(Base, Identified):
    __tablename__ = "runs"
    session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id"), index=True)
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id"))
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    input: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    stage: Mapped[str | None] = mapped_column(String(40))
    outcome_reason: Mapped[str | None] = mapped_column(String(200))
    warnings: Mapped[list] = mapped_column(J, default=list)
    error: Mapped[dict | None] = mapped_column(J)
    policy_version: Mapped[str] = mapped_column(String(50), default="v2-independent-identity")
    model_versions: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    current_draft_id: Mapped[str | None] = mapped_column(String(36))


class Job(Base, Identified):
    __tablename__ = "jobs"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="research")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    instructions: Mapped[str | None] = mapped_column(String(1000))


class Artifact(Base, Identified):
    __tablename__ = "artifacts"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict] = mapped_column(J)
    __table_args__ = (UniqueConstraint("run_id", "kind", "id"),)


class Draft(Base, Identified):
    __tablename__ = "drafts"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(J)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    validation_findings: Mapped[list] = mapped_column(J, default=list)
    origin: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    __table_args__ = (UniqueConstraint("run_id", "version"),)


class Review(Base, Identified):
    __tablename__ = "reviews"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id"))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class Event(Base, Identified):
    __tablename__ = "run_events"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(50))
    stage: Mapped[str | None] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(J, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)


class ProviderCall(Base, Identified):
    __tablename__ = "provider_calls"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    data: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class Idempotency(Base, Identified):
    __tablename__ = "idempotency"
    session_id: Mapped[str] = mapped_column(ForeignKey("demo_sessions.id"))
    key: Mapped[str] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    __table_args__ = (UniqueConstraint("session_id", "key"),)


class Quota(Base):
    __tablename__ = "quotas"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


Index(
    "one_active_job",
    Job.run_id,
    unique=True,
    postgresql_where=Job.status.in_(["queued", "leased"]),
    sqlite_where=Job.status.in_(["queued", "leased"]),
)


class SourceRecord(Base, Identified):
    __tablename__ = "sources"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2048))
    data: Mapped[dict] = mapped_column(J)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    __table_args__ = (
        UniqueConstraint("run_id", "source_key"),
        UniqueConstraint("run_id", "url"),
    )


class ClaimRecord(Base, Identified):
    __tablename__ = "claims"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    claim_key: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(J)
    __table_args__ = (UniqueConstraint("run_id", "claim_key"),)


class ClaimSource(Base):
    __tablename__ = "claim_sources"
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), primary_key=True)


class SignalRecord(Base, Identified):
    __tablename__ = "signals"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    data: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
