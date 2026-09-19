"""Custom project statuses, multi roles, drop legacy flags.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_STATUSES = [
    ("Live", "live", 1, True),
    ("Offline", "offline", 2, True),
    ("Maintenance", "maintenance", 3, True),
    ("Archived", "archived", 4, False),
]


def upgrade() -> None:
    op.create_table(
        "ap_project_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "show_in_list",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_ap_project_statuses_name"),
        sa.UniqueConstraint("slug", name="uq_ap_project_statuses_slug"),
    )

    op.create_table(
        "ap_project_role_links",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ap_projects.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("role_name", sa.String(80), primary_key=True, nullable=False),
    )

    # Seed statuses with fixed UUIDv7-like deterministic hex for migration mapping
    conn = op.get_bind()
    seed_ids: dict[str, str] = {}
    for name, slug, sequence, show_in_list in SEED_STATUSES:
        row = conn.execute(
            sa.text(
                """
                INSERT INTO ap_project_statuses (id, name, slug, sequence, show_in_list)
                VALUES (gen_random_uuid(), :name, :slug, :sequence, :show_in_list)
                RETURNING id
                """
            ),
            {
                "name": name,
                "slug": slug,
                "sequence": sequence,
                "show_in_list": show_in_list,
            },
        ).one()
        seed_ids[slug] = str(row[0])

    op.add_column(
        "ap_projects",
        sa.Column("status_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Map old string status -> new status_id
    for slug, status_id in seed_ids.items():
        conn.execute(
            sa.text(
                """
                UPDATE ap_projects
                SET status_id = CAST(:sid AS uuid)
                WHERE lower(status) = :slug
                """
            ),
            {"sid": status_id, "slug": slug},
        )

    # Anything unmatched -> offline
    offline_id = seed_ids["offline"]
    conn.execute(
        sa.text(
            """
            UPDATE ap_projects
            SET status_id = CAST(:sid AS uuid)
            WHERE status_id IS NULL
            """
        ),
        {"sid": offline_id},
    )

    # Migrate single required_role_name into link table
    conn.execute(
        sa.text(
            """
            INSERT INTO ap_project_role_links (project_id, role_name)
            SELECT id, required_role_name
            FROM ap_projects
            WHERE required_role_name IS NOT NULL AND btrim(required_role_name) <> ''
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.alter_column("ap_projects", "status_id", nullable=False)
    op.create_foreign_key(
        "ap_projects_status_id_fkey",
        "ap_projects",
        "ap_project_statuses",
        ["status_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_ap_projects_status_id", "ap_projects", ["status_id"])

    op.drop_column("ap_projects", "status")
    op.drop_column("ap_projects", "can_go_live")
    op.drop_column("ap_projects", "is_public")
    op.drop_column("ap_projects", "required_role_name")
    op.drop_column("ap_projects", "is_external")
    op.drop_column("ap_projects", "external_url")


def downgrade() -> None:
    op.add_column(
        "ap_projects",
        sa.Column("status", sa.String(30), server_default="offline", nullable=False),
    )
    op.add_column(
        "ap_projects",
        sa.Column("can_go_live", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "ap_projects",
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "ap_projects",
        sa.Column("required_role_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "ap_projects",
        sa.Column("is_external", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "ap_projects",
        sa.Column("external_url", sa.String(500), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE ap_projects p
            SET status = s.slug
            FROM ap_project_statuses s
            WHERE p.status_id = s.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE ap_projects p
            SET required_role_name = (
                SELECT r.role_name
                FROM ap_project_role_links r
                WHERE r.project_id = p.id
                ORDER BY r.role_name
                LIMIT 1
            )
            """
        )
    )

    op.drop_constraint("ap_projects_status_id_fkey", "ap_projects", type_="foreignkey")
    op.drop_index("ix_ap_projects_status_id", table_name="ap_projects")
    op.drop_column("ap_projects", "status_id")
    op.drop_table("ap_project_role_links")
    op.drop_table("ap_project_statuses")
