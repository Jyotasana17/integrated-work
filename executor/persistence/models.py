import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Float, Enum, Text, Boolean
from sqlalchemy.orm import relationship
import enum

from executor.persistence.database import Base


# Cross-database GUID type: uses PostgreSQL UUID where available, falls back to CHAR(36)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value if dialect.name == "postgresql" else str(value)
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WorkerStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


def utcnow():
    return datetime.now(timezone.utc)


class Scan(Base):
    __tablename__ = "scans"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    target = Column(String(1024), nullable=False)  # Base URL or target
    status = Column(String(50), default=ScanStatus.PENDING.value, index=True)
    config = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship("Task", back_populates="scan", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    scan_id = Column(GUID(), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)

    method = Column(String(10), nullable=False)  # GET, POST, etc
    url = Column(String(2048), nullable=False)
    headers = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)

    status = Column(String(50), default=TaskStatus.QUEUED.value, index=True)
    attempts = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    scan = relationship("Scan", back_populates="tasks")
    response = relationship("ScanResponse", back_populates="task", uselist=False, cascade="all, delete-orphan")


class ScanResponse(Base):
    __tablename__ = "scan_responses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    task_id = Column(GUID(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True)

    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    response_headers = Column(JSON, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    task = relationship("Task", back_populates="response")


class Worker(Base):
    __tablename__ = "workers"

    id = Column(String(255), primary_key=True)  # e.g. hostname + pid
    status = Column(String(50), default=WorkerStatus.ONLINE.value)
    active_tasks = Column(Integer, default=0)
    last_heartbeat = Column(DateTime(timezone=True), default=utcnow)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.USER.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RevokedToken(Base):
    """Stores the JTI of access/refresh tokens that have been invalidated
    (logout / refresh rotation), so they can no longer be used."""
    __tablename__ = "revoked_tokens"

    jti = Column(String(64), primary_key=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
