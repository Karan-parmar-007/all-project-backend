"""Add app_key to projects and allows_access to statuses.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ap_projects",
        sa.Column("app_key", sa.String(80), nullable=True),
    )
    op.create_index(
        "uq_ap_projects_app_key",
        "ap_projects",
        ["app_key"],
        unique=True,
        postgresql_where=sa.text("app_key IS NOT NULL"),
    )

    op.add_column(
        "ap_project_statuses",
        sa.Column(
            "allows_access",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    # Live status allows runtime access; everything else stays blocked.
    op.execute(
        sa.text(
            "UPDATE ap_project_statuses SET allows_access = true WHERE slug = 'live'"
        )
    )


def downgrade() -> None:
    op.drop_column("ap_project_statuses", "allows_access")
    op.drop_index("uq_ap_projects_app_key", table_name="ap_projects")
    op.drop_column("ap_projects", "app_key")
