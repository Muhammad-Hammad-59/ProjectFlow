"""ProjectFlow ORM models (SQLAlchemy 2.x, PostgreSQL 15+).

These mirror schema.sql column for column. Alembic autogenerates tables,
columns, indexes and foreign keys from this file; the triggers (loop check,
one-owner rule, subtask depth, append-only log, updated_at) are created by
the initial Alembic migration, because autogenerate does not see triggers.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Value sets, shared with Pydantic schemas so API and DB agree.
ROLES = ("owner", "member", "viewer")
TASK_KINDS = ("task", "milestone")
TASK_STATUSES = ("todo", "in_progress", "in_review", "done")
PRIORITIES = ("low", "medium", "high", "urgent")
ESTIMATE_UNITS = ("hours", "days")
SPRINT_STATUSES = ("planned", "active", "completed")
NOTIFICATION_TYPES = (
    "task_assigned", "mentioned", "predecessor_late", "task_overdue",
    "project_late", "invited", "role_changed",
)
ENTITY_TYPES = (
    "workspace", "membership", "invitation", "holiday", "project", "sprint",
    "task", "dependency", "comment", "attachment", "time_entry", "baseline",
)
ACTIONS = ("created", "updated", "deleted", "restored", "archived", "unarchived", "moved", "rescheduled")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


TZ = TIMESTAMP(timezone=True)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "%(table_name)s_%(column_0_N_name)s_idx",
            "uq": "%(table_name)s_%(column_0_N_name)s_key",
            "ck": "%(table_name)s_%(constraint_name)s",
            "fk": "%(table_name)s_%(column_0_N_name)s_fkey",
            "pk": "%(table_name)s_pkey",
        }
    )
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: TZ,
        dict[str, Any]: JSONB,
    }


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def created() -> Mapped[datetime]:
    return mapped_column(TZ, nullable=False, server_default=func.now())


def updated() -> Mapped[datetime]:
    # The database trigger set_updated_at keeps this current; onupdate keeps
    # the ORM's copy fresh without a refresh.
    return mapped_column(TZ, nullable=False, server_default=func.now(), onupdate=func.now())


# =====================================================================
# 1. Identity and workspace
# =====================================================================

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        CheckConstraint(r"email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'", name="email_format"),
        CheckConstraint("char_length(btrim(full_name)) BETWEEN 1 AND 120", name="full_name_len"),
    )

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    email_verified_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    memberships: Mapped[list[Membership]] = relationship(back_populates="user", passive_deletes=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="refresh_tokens_token_hash_key"),
        Index("refresh_tokens_user_idx", "user_id"),
        Index("refresh_tokens_family_idx", "family_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None]
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_tokens.id", ondelete="SET NULL"))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = created()


class PasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        UniqueConstraint("token_hash", name="password_resets_token_hash_key"),
        Index("password_resets_user_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("slug", name="workspaces_slug_key"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 48", name="slug_format"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        CheckConstraint(
            "cardinality(working_days) BETWEEN 1 AND 7 AND working_days <@ '{1,2,3,4,5,6,7}'::smallint[]",
            name="working_days_valid",
        ),
        CheckConstraint("hours_per_day > 0 AND hours_per_day <= 24", name="hours_per_day_range"),
    )

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    working_days: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, server_default=text("'{1,2,3,4,5}'")
    )
    hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, server_default=text("8"))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    memberships: Mapped[list[Membership]] = relationship(back_populates="workspace", passive_deletes=True)
    holidays: Mapped[list[Holiday]] = relationship(passive_deletes=True, order_by="Holiday.holiday_date")
    projects: Mapped[list[Project]] = relationship(back_populates="workspace", passive_deletes=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "user_id", name="memberships_pkey"),
        CheckConstraint(_in("role", ROLES), name="role_valid"),
        Index("memberships_user_idx", "user_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text, nullable=False)
    joined_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="invitations_token_hash_key"),
        CheckConstraint(_in("role", ROLES), name="role_valid"),
        CheckConstraint("accepted_at IS NULL OR revoked_at IS NULL", name="single_outcome"),
        Index(
            "invitations_one_open_idx", "workspace_id", "email", unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    accepted_at: Mapped[datetime | None]
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()


class Holiday(Base):
    __tablename__ = "holidays"
    __table_args__ = (
        UniqueConstraint("workspace_id", "holiday_date", name="holidays_one_per_day"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created()


# =====================================================================
# 2. Projects and tasks
# =====================================================================

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="projects_workspace_id_id_key"),
        UniqueConstraint("workspace_id", "key", name="projects_key_per_workspace"),
        CheckConstraint("key ~ '^[A-Z][A-Z0-9]{1,9}$'", name="key_format"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 120", name="name_len"),
        CheckConstraint("target_end_date >= start_date", name="dates_order"),
        CheckConstraint("next_task_number > 0", name="next_task_number_positive"),
        Index("projects_active_idx", "workspace_id", "name", postgresql_where=text("archived_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    projected_end_date: Mapped[date | None] = mapped_column(Date)
    scheduled_at: Mapped[datetime | None]
    next_task_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    archived_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    # Optimistic locking: UPDATE ... WHERE version = :read_version
    __mapper_args__ = {"version_id_col": version}

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="project", passive_deletes=True, foreign_keys="Task.project_id",
        primaryjoin="Project.id == Task.project_id",
    )
    dependencies: Mapped[list[Dependency]] = relationship(
        primaryjoin="Project.id == Dependency.project_id",
        foreign_keys="Dependency.project_id", viewonly=True,
    )


class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="sprints_project_id_id_key"),
        CheckConstraint(_in("status", SPRINT_STATUSES), name="status_valid"),
        CheckConstraint("end_date >= start_date", name="dates_order"),
        Index("sprints_one_active_idx", "project_id", unique=True, postgresql_where=text("status = 'active'")),
    )

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="planned")
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="tasks_workspace_id_id_key"),
        UniqueConstraint("project_id", "id", name="tasks_project_id_id_key"),
        UniqueConstraint("project_id", "number", name="tasks_number_per_project"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="tasks_project_fkey", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "parent_id"], ["tasks.project_id", "tasks.id"],
            name="tasks_parent_fkey", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "sprint_id"], ["sprints.project_id", "sprints.id"],
            name="tasks_sprint_fkey", ondelete="SET NULL (sprint_id)",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "owner_id"], ["memberships.workspace_id", "memberships.user_id"],
            name="tasks_owner_fkey", ondelete="SET NULL (owner_id)",
        ),
        CheckConstraint("number > 0", name="number_positive"),
        CheckConstraint(_in("kind", TASK_KINDS), name="kind_valid"),
        CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 200", name="title_len"),
        CheckConstraint(_in("status", TASK_STATUSES), name="status_valid"),
        CheckConstraint(_in("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint(_in("estimate_unit", ESTIMATE_UNITS), name="estimate_unit_valid"),
        CheckConstraint("estimate >= 0 AND estimate <= 9999", name="estimate_range"),
        CheckConstraint("kind = 'task' OR estimate = 0", name="milestone_no_estimate"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
        CheckConstraint(
            "scheduled_start IS NULL OR scheduled_end IS NULL OR scheduled_end >= scheduled_start",
            name="schedule_order",
        ),
        CheckConstraint("slack_days IS NULL OR slack_days >= 0", name="slack_nonnegative"),
        CheckConstraint("(status = 'done') = (completed_at IS NOT NULL)", name="done_has_completed_at"),
        Index("tasks_board_idx", "project_id", "status", "position", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "tasks_owner_schedule_idx", "owner_id", "scheduled_start", "scheduled_end",
            postgresql_where=text("deleted_at IS NULL AND status <> 'done'"),
        ),
        Index(
            "tasks_open_by_end_idx", "project_id", "scheduled_end",
            postgresql_where=text("deleted_at IS NULL AND status <> 'done'"),
        ),
        Index("tasks_parent_idx", "parent_id", postgresql_where=text("parent_id IS NOT NULL")),
        Index("tasks_sprint_idx", "sprint_id", postgresql_where=text("sprint_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    parent_id: Mapped[uuid.UUID | None]
    sprint_id: Mapped[uuid.UUID | None]
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="task")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="todo")
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default="medium")
    estimate: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, server_default=text("0"))
    estimate_unit: Mapped[str] = mapped_column(Text, nullable=False, server_default="days")
    start_no_earlier_than: Mapped[date | None] = mapped_column(Date)
    position: Mapped[str] = mapped_column(Text(collation="C"), nullable=False)
    scheduled_start: Mapped[date | None] = mapped_column(Date)
    scheduled_end: Mapped[date | None] = mapped_column(Date)
    slack_days: Mapped[int | None] = mapped_column(Integer)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    __mapper_args__ = {"version_id_col": version}

    project: Mapped[Project] = relationship(
        back_populates="tasks", foreign_keys="Task.project_id", primaryjoin="Task.project_id == Project.id",
    )
    parent: Mapped[Task | None] = relationship(
        back_populates="subtasks", remote_side="Task.id", foreign_keys="Task.parent_id",
        primaryjoin="Task.parent_id == Task.id",
    )
    subtasks: Mapped[list[Task]] = relationship(
        back_populates="parent", foreign_keys="Task.parent_id", primaryjoin="Task.id == Task.parent_id",
        passive_deletes=True,
    )
    owner: Mapped[User | None] = relationship(
        primaryjoin="Task.owner_id == User.id", foreign_keys="Task.owner_id", viewonly=True,
    )
    predecessor_links: Mapped[list[Dependency]] = relationship(
        primaryjoin="Task.id == Dependency.successor_id", foreign_keys="Dependency.successor_id",
        back_populates="successor", passive_deletes=True,
    )
    successor_links: Mapped[list[Dependency]] = relationship(
        primaryjoin="Task.id == Dependency.predecessor_id", foreign_keys="Dependency.predecessor_id",
        back_populates="predecessor", passive_deletes=True,
    )
    labels: Mapped[list[Label]] = relationship(secondary="task_labels", viewonly=True)
    comments: Mapped[list[Comment]] = relationship(
        back_populates="task", passive_deletes=True, order_by="Comment.created_at",
    )

    @property
    def key(self) -> str:
        return f"{self.project.key}-{self.number}"


class Dependency(Base):
    """successor cannot start until predecessor is done (finish-to-start)."""

    __tablename__ = "dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "predecessor_id"], ["tasks.project_id", "tasks.id"],
            name="dependencies_predecessor_fkey", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "successor_id"], ["tasks.project_id", "tasks.id"],
            name="dependencies_successor_fkey", ondelete="CASCADE",
        ),
        UniqueConstraint("predecessor_id", "successor_id", name="dependencies_pair_key"),
        CheckConstraint("predecessor_id <> successor_id", name="not_self"),
        Index("dependencies_successor_idx", "successor_id"),
        Index("dependencies_project_idx", "project_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    predecessor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    successor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created()

    predecessor: Mapped[Task] = relationship(
        primaryjoin="Dependency.predecessor_id == Task.id", foreign_keys="Dependency.predecessor_id",
        back_populates="successor_links",
    )
    successor: Mapped[Task] = relationship(
        primaryjoin="Dependency.successor_id == Task.id", foreign_keys="Dependency.successor_id",
        back_populates="predecessor_links",
    )


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="labels_workspace_id_id_key"),
        UniqueConstraint("workspace_id", "name", name="labels_name_per_workspace"),
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 40", name="name_len"),
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="color_hex"),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False, server_default="#64748B")
    created_at: Mapped[datetime] = created()


class TaskLabel(Base):
    __tablename__ = "task_labels"
    __table_args__ = (
        PrimaryKeyConstraint("task_id", "label_id", name="task_labels_pkey"),
        ForeignKeyConstraint(
            ["workspace_id", "task_id"], ["tasks.workspace_id", "tasks.id"],
            name="task_labels_task_fkey", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "label_id"], ["labels.workspace_id", "labels.id"],
            name="task_labels_label_fkey", ondelete="CASCADE",
        ),
        Index("task_labels_label_idx", "label_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    task_id: Mapped[uuid.UUID]
    label_id: Mapped[uuid.UUID]


# =====================================================================
# 3. Collaboration
# =====================================================================

class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("char_length(btrim(body)) BETWEEN 1 AND 10000", name="body_len"),
        Index("comments_task_idx", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()

    task: Mapped[Task] = relationship(back_populates="comments")
    author: Mapped[User | None] = relationship()
    mentions: Mapped[list[CommentMention]] = relationship(passive_deletes=True, cascade="all, delete-orphan")


class CommentMention(Base):
    __tablename__ = "comment_mentions"
    __table_args__ = (
        PrimaryKeyConstraint("comment_id", "user_id", name="comment_mentions_pkey"),
        Index("comment_mentions_user_idx", "user_id"),
    )

    comment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class TimeEntry(Base):
    __tablename__ = "time_entries"
    __table_args__ = (
        CheckConstraint("minutes BETWEEN 1 AND 1440", name="minutes_range"),
        Index("time_entries_task_idx", "task_id"),
        Index("time_entries_user_day_idx", "user_id", "work_date"),
    )

    id: Mapped[uuid.UUID] = pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = updated()


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("storage_key", name="attachments_storage_key_key"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 26214400", name="size_range"),
        CheckConstraint("char_length(file_name) BETWEEN 1 AND 255", name="file_name_len"),
        Index("attachments_task_idx", "task_id", postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()


# =====================================================================
# 4. Audit and reporting
# =====================================================================

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(_in("type", NOTIFICATION_TYPES), name="type_valid"),
        Index("notifications_inbox_idx", "recipient_id", text("created_at DESC")),
        Index("notifications_unread_idx", "recipient_id", postgresql_where=text("read_at IS NULL")),
        Index(
            "notifications_dedupe_idx", "recipient_id", "dedupe_key", unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    comment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created()


class ActivityLog(Base):
    __tablename__ = "activity_log"
    __table_args__ = (
        CheckConstraint(_in("entity_type", ENTITY_TYPES), name="entity_type_valid"),
        CheckConstraint(_in("action", ACTIONS), name="action_valid"),
        Index("activity_log_project_idx", "project_id", text("created_at DESC")),
        Index("activity_log_entity_idx", "entity_type", "entity_id", text("created_at DESC")),
        Index("activity_log_workspace_idx", "workspace_id", text("created_at DESC")),
        Index("activity_log_task_idx", "task_id", text("created_at DESC"), postgresql_where=text("task_id IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[uuid.UUID | None]  # no FK on purpose: history outlives the task
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    request_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = created()


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("project_id", "name", name="baselines_name_per_project"),)

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    projected_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created()

    tasks: Mapped[list[BaselineTask]] = relationship(passive_deletes=True, cascade="all, delete-orphan")


class BaselineTask(Base):
    __tablename__ = "baseline_tasks"
    __table_args__ = (PrimaryKeyConstraint("baseline_id", "task_id", name="baseline_tasks_pkey"),)

    baseline_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("baselines.id", ondelete="CASCADE"))
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    estimate: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    estimate_unit: Mapped[str] = mapped_column(Text, nullable=False)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
