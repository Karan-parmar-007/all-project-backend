"""Add show_on_home / show_in_about flags to all_projects skills.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ap_skill_categories",
        sa.Column(
            "show_on_home",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "ap_skills",
        sa.Column(
            "show_in_about",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "skill_categories" in tables:
        op.execute(
            """
            UPDATE ap_skill_categories AS a
            SET show_on_home = s.show_on_home
            FROM skill_categories AS s
            WHERE a.id = s.id OR a.name = s.name
            """
        )
    if "skills" in tables:
        op.execute(
            """
            UPDATE ap_skills AS a
            SET show_in_about = s.show_in_about
            FROM skills AS s
            WHERE a.id = s.id OR a.name = s.name
            """
        )


def downgrade() -> None:
    op.drop_column("ap_skills", "show_in_about")
    op.drop_column("ap_skill_categories", "show_on_home")
