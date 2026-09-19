# app/api/routes/skill/model.py
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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel, func


class ApSkillCategory(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_skill_categories"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    name: str = Field(sa_column=Column(String(100), unique=True, nullable=False))
    sequence: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))
    show_on_home: bool = Field(
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

    skills: list["ApSkill"] = Relationship(back_populates="category")


class ApSkill(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ap_skills"

    id: UUID = Field(default_factory=uuid6.uuid7, primary_key=True)
    name: str = Field(sa_column=Column(String(100), unique=True, nullable=False))
    category_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("ap_skill_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    sequence: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))
    icon_key: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    show_in_about: bool = Field(
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

    category: Optional[ApSkillCategory] = Relationship(back_populates="skills")
