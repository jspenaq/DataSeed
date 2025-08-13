#!/usr/bin/env python3
"""
Verification script to check the sources table contents.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

from app.config import settings


def main():
    """Verify sources in the database."""
    print("Verifying sources in database...")

    # Create sync engine
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    # Query sources
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, name, type, base_url, rate_limit, is_active, created_at FROM sources ORDER BY id"),
        )
        sources = result.fetchall()

        print("Sources in database:")
        print("=" * 80)
        for source in sources:
            print(f"ID: {source.id}")
            print(f"Name: {source.name}")
            print(f"Type: {source.type}")
            print(f"Base URL: {source.base_url}")
            print(f"Rate Limit: {source.rate_limit}")
            print(f"Active: {source.is_active}")
            print(f"Created: {source.created_at}")
            print("-" * 40)

        print(f"Total sources: {len(sources)}")

        # Verify expected sources
        expected_sources = {"hackernews", "reddit", "github", "producthunt"}
        actual_sources = {source.name for source in sources}

        if expected_sources == actual_sources:
            print("✅ All expected sources are present!")
        else:
            missing = expected_sources - actual_sources
            extra = actual_sources - expected_sources
            if missing:
                print(f"❌ Missing sources: {missing}")
            if extra:
                print(f"⚠️  Extra sources: {extra}")


if __name__ == "__main__":
    main()
