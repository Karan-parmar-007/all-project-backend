#!/usr/bin/env python3
"""Migrate existing projects from new_backend (projects, project_skills) to ap_projects.

Usage:
    python migrate_projects_from_new_backend.py --dry-run
    python migrate_projects_from_new_backend.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import sys
import os

BASE_DIR = Path("/home/karan/my_website/all_projects/backend")
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

from app.config import db_settings
from app.api.routes.project.model import (
    ApProject,
    ApProjectTag,
    ApProjectTagLink,
)

logger = logging.getLogger("migrate_projects")


async def migrate(dry_run: bool = False) -> None:
    engine = create_async_engine(db_settings.POSTGRES_URL, echo=False)
    
    async with engine.begin() as conn:
        src_res = await conn.execute(text("""
            SELECT p.id, p.name, p.slug, p.short_description, p.long_description,
                   p.is_featured, p.is_live, p.live_url, p.github_link_backend,
                   p.github_link_frontend, p.sequence, p.created_at, p.updated_at
            FROM projects p
            ORDER BY p.sequence ASC;
        """))
        source_projects = src_res.mappings().all()
        logger.info("Found %d projects in 'projects' table to migrate.", len(source_projects))

        migrated_count = 0
        tag_count = 0
        link_count = 0

        for p in source_projects:
            pid: UUID = p["id"]
            slug: str = p["slug"]
            name: str = p["name"]

            skill_res = await conn.execute(text("""
                SELECT s.name
                FROM skills s
                JOIN project_skills ps ON ps.skill_id = s.id
                WHERE ps.project_id = :pid
            """), {"pid": pid})
            skill_names = [r[0].strip() for r in skill_res.fetchall()]

            github_url = p["github_link_backend"] or p["github_link_frontend"] or None

            project_dict = {
                "id": pid,
                "name": name,
                "slug": slug,
                "short_description": p["short_description"],
                "long_description": p["long_description"] or p["short_description"],
                "can_go_live": False,  # User confirmed: all current projects cannot go live
                "status": "offline",
                "is_public": True,
                "required_role_name": None,
                "is_featured": p["is_featured"],
                "sequence": p["sequence"] or 0,
                "live_url": p["live_url"],
                "github_url": github_url,
                "is_external": False,
                "external_url": None,
                "cover_image_key": None,
                "tech_stack": skill_names,
                "created_at": p["created_at"],
                "updated_at": p["updated_at"],
            }

            logger.info("[%s] %s (skills: %s)", "DRY-RUN" if dry_run else "MIGRATE", name, skill_names)

            if not dry_run:
                stmt = pg_insert(ApProject).values(**project_dict)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["slug"],
                    set_={
                        "name": stmt.excluded.name,
                        "short_description": stmt.excluded.short_description,
                        "long_description": stmt.excluded.long_description,
                        "can_go_live": stmt.excluded.can_go_live,
                        "status": stmt.excluded.status,
                        "is_public": stmt.excluded.is_public,
                        "is_featured": stmt.excluded.is_featured,
                        "sequence": stmt.excluded.sequence,
                        "live_url": stmt.excluded.live_url,
                        "github_url": stmt.excluded.github_url,
                        "tech_stack": stmt.excluded.tech_stack,
                        "updated_at": stmt.excluded.updated_at,
                    }
                )
                await conn.execute(stmt)
                migrated_count += 1

                for s_name in skill_names:
                    tag_norm = s_name.lower().strip()
                    t_res = await conn.execute(
                        text("SELECT id FROM ap_project_tags WHERE name = :name"),
                        {"name": tag_norm}
                    )
                    t_row = t_res.fetchone()
                    if t_row:
                        tag_id = t_row[0]
                    else:
                        import uuid6
                        tag_id = uuid6.uuid7()
                        await conn.execute(
                            text("INSERT INTO ap_project_tags (id, name, created_at) VALUES (:id, :name, now())"),
                            {"id": tag_id, "name": tag_norm}
                        )
                        tag_count += 1

                    link_stmt = pg_insert(ApProjectTagLink).values(
                        project_id=pid,
                        tag_id=tag_id,
                    ).on_conflict_do_nothing()
                    await conn.execute(link_stmt)
                    link_count += 1

        logger.info(
            "Migration summary (%s): %d projects processed, %d tags created, %d tag links created.",
            "DRY-RUN" if dry_run else "SUCCESS",
            len(source_projects) if dry_run else migrated_count,
            tag_count,
            link_count,
        )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate projects from new_backend to ap_projects")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be migrated without making changes")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
