"""Daily scrape usage table (companies are never stored).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ap_scraper_daily_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "companies_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "day", name="uq_ap_scraper_daily_usage_user_day"
        ),
    )
    op.create_index(
        "ix_ap_scraper_daily_usage_user_id",
        "ap_scraper_daily_usage",
        ["user_id"],
    )
    op.create_index(
        "ix_ap_scraper_daily_usage_day",
        "ap_scraper_daily_usage",
        ["day"],
    )


def downgrade() -> None:
    op.drop_index("ix_ap_scraper_daily_usage_day", table_name="ap_scraper_daily_usage")
    op.drop_index(
        "ix_ap_scraper_daily_usage_user_id", table_name="ap_scraper_daily_usage"
    )
    op.drop_table("ap_scraper_daily_usage")
