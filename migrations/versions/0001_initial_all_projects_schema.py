"""Initial all_projects schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ap_media_assets ──────────────────────────────────────────────────
    op.create_table(
        "ap_media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_ap_media_assets_checksum_sha256", "ap_media_assets", ["checksum_sha256"])
    op.create_index("ix_ap_media_assets_kind", "ap_media_assets", ["kind"])

    # ── ap_project_tags ──────────────────────────────────────────────────
    op.create_table(
        "ap_project_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── ap_projects ──────────────────────────────────────────────────────
    op.create_table(
        "ap_projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=False),
        sa.Column("long_description", sa.Text(), nullable=False),
        sa.Column("can_go_live", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(30), server_default="offline", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("required_role_name", sa.String(50), nullable=True),
        sa.Column("is_featured", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("live_url", sa.String(500), nullable=True),
        sa.Column("github_url", sa.String(500), nullable=True),
        sa.Column("is_external", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column(
            "cover_image_media_id",
            sa.Uuid(),
            sa.ForeignKey("ap_media_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tech_stack",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    # ── ap_project_tag_links ─────────────────────────────────────────────
    op.create_table(
        "ap_project_tag_links",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("ap_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("ap_project_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("project_id", "tag_id"),
    )

    # ── ap_project_screenshots ───────────────────────────────────────────
    op.create_table(
        "ap_project_screenshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("ap_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "media_id",
            sa.Uuid(),
            sa.ForeignKey("ap_media_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ap_project_screenshots")
    op.drop_table("ap_project_tag_links")
    op.drop_table("ap_projects")
    op.drop_table("ap_project_tags")
    op.drop_index("ix_ap_media_assets_kind", table_name="ap_media_assets")
    op.drop_index("ix_ap_media_assets_checksum_sha256", table_name="ap_media_assets")
    op.drop_table("ap_media_assets")
