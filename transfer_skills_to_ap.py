#!/usr/bin/env python3
"""Transfer skills and categories from new_backend into ap_skills & ap_skill_categories."""
import asyncio
from pathlib import Path
import sys
import os

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import db_settings

async def transfer():
    engine = create_async_engine(db_settings.POSTGRES_URL)
    async with engine.begin() as conn:
        # 1. Fetch existing skill_categories
        cat_res = await conn.execute(text("SELECT id, name, sequence FROM skill_categories WHERE name != 'test' ORDER BY sequence ASC;"))
        cats = cat_res.mappings().all()
        print(f"Found {len(cats)} skill categories to migrate.")

        for c in cats:
            await conn.execute(text("""
                INSERT INTO ap_skill_categories (id, name, sequence, created_at, updated_at)
                VALUES (:id, :name, :sequence, now(), now())
                ON CONFLICT (name) DO UPDATE SET sequence = EXCLUDED.sequence, updated_at = now();
            """), {"id": c["id"], "name": c["name"], "sequence": c["sequence"]})

        # 2. Fetch existing skills
        skill_res = await conn.execute(text("""
            SELECT s.id, s.name, s.category_id, s.sequence
            FROM skills s
            JOIN skill_categories c ON s.category_id = c.id
            WHERE c.name != 'test'
            ORDER BY s.sequence ASC;
        """))
        skills = skill_res.mappings().all()
        print(f"Found {len(skills)} skills to migrate.")

        for s in skills:
            await conn.execute(text("""
                INSERT INTO ap_skills (id, name, category_id, sequence, created_at, updated_at)
                VALUES (:id, :name, :category_id, :sequence, now(), now())
                ON CONFLICT (name) DO UPDATE SET category_id = EXCLUDED.category_id, sequence = EXCLUDED.sequence, updated_at = now();
            """), {"id": s["id"], "name": s["name"], "category_id": s["category_id"], "sequence": s["sequence"]})

        # Count in ap_skills
        count = (await conn.execute(text("SELECT count(*) FROM ap_skills;"))).scalar()
        print(f"Transfer complete! Total ap_skills: {count}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(transfer())
