# app/api/routes/project/model.py
from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID

import uuid6
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel, func


class ApProjectStatus(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_project_statuses"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    name: str = Field(sa_column=Column(String(80), unique=True, nullable=False))
    slug: str = Field(sa_column=Column(String(80), unique=True, nullable=False))
    sequence: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))
    show_in_list: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    allows_access: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )


class ApProjectTag(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_project_tags"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    name: str = Field(sa_column=Column(String(50), unique=True, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    )


class ApProjectTagLink(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_project_tag_links"

    project_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_projects.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    tag_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_project_tags.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class ApProjectRoleLink(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_project_role_links"

    project_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_projects.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    role_name: str = Field(sa_column=Column(String(80), primary_key=True))


class ApProjectScreenshot(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_project_screenshots"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    project_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_projects.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    image_key: str = Field(sa_column=Column(String(500), nullable=False))
    caption: Optional[str] = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    sequence: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))


class ApProject(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_projects"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    name: str = Field(sa_column=Column(String(150), unique=True, nullable=False))
    slug: str = Field(sa_column=Column(String(180), unique=True, nullable=False))
    short_description: str = Field(sa_column=Column(Text, nullable=False))
    long_description: str = Field(sa_column=Column(Text, nullable=False))

    status_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_project_statuses.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )

    is_featured: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    sequence: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))

    live_url: Optional[str] = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )
    # Immutable code-module key for embedded live apps (e.g. advance_scraper).
    app_key: Optional[str] = Field(
        default=None,
        sa_column=Column(String(80), nullable=True, unique=True),
    )
    github_url: Optional[str] = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )

    cover_image_key: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    tech_stack: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )
