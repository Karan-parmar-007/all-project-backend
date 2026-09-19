"""Remove media_assets and use direct cover_image_key.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update ap_projects: add cover_image_key, drop FK and cover_image_media_id
    op.add_column("ap_projects", sa.Column("cover_image_key", sa.String(500), nullable=True))
    op.drop_constraint("ap_projects_cover_image_media_id_fkey", "ap_projects", type_="foreignkey")
    op.drop_column("ap_projects", "cover_image_media_id")

    # 2. Update ap_project_screenshots: add image_key, drop media_id FK
    op.add_column("ap_project_screenshots", sa.Column("image_key", sa.String(500), nullable=True))
    op.drop_constraint("ap_project_screenshots_media_id_fkey", "ap_project_screenshots", type_="foreignkey")
    op.drop_column("ap_project_screenshots", "media_id")

    # 3. Drop ap_media_assets table
    op.drop_index("ix_ap_media_assets_kind", table_name="ap_media_assets")
    op.drop_index("ix_ap_media_assets_checksum_sha256", table_name="ap_media_assets")
    op.drop_table("ap_media_assets")


def downgrade() -> None:
    pass
