#!/usr/bin/env python3
"""
Seed script to populate the sources table with initial data.

This script creates the four main data sources (HackerNews, Reddit, GitHub, ProductHunt)
with their proper API endpoints and rate limits. It's idempotent and can be run multiple times safely.
"""

import sys
from pathlib import Path
from typing import Any

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.source import Source


def create_sync_engine() -> Engine:
    """Create a synchronous database engine for seeding."""
    # Convert async URL to sync URL
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    return create_engine(sync_url, echo=True)


def get_sources_data() -> list[dict[str, Any]]:
    """Return the sources data to be seeded."""
    return [
        {
            "name": "hackernews",
            "type": "api",
            "base_url": "https://hacker-news.firebaseio.com/v0",
            "rate_limit": 600,
            "config": {"items_endpoint": "/topstories.json", "detail_endpoint": "/item/{id}.json"},
            "is_active": True,
        },
        {
            "name": "reddit",
            "type": "api",
            "base_url": "https://oauth.reddit.com",
            "rate_limit": 60,
            "config": {
                "subreddit": "all",
                "client_id": "${REDDIT_CLIENT_ID}",
                "client_secret": "${REDDIT_CLIENT_SECRET}",
            },
            "is_active": True,
        },
        {
            "name": "github",
            "type": "api",
            "base_url": "https://api.github.com",
            "rate_limit": 5000,
            "config": {"search_endpoint": "/search/repositories", "token": "${GITHUB_TOKEN}"},
            "is_active": True,
        },
        {
            "name": "producthunt",
            "type": "api",
            "base_url": "https://api.producthunt.com/v2",
            "rate_limit": 500,
            "config": {"token": "${PRODUCTHUNT_TOKEN}"},
            "is_active": True,
        },
    ]


def seed_sources(session: Session) -> None:
    """
    Seed the sources table with initial data.

    Args:
        session: SQLAlchemy session
    """
    sources_data = get_sources_data()

    print(f"Seeding {len(sources_data)} sources...")

    for source_data in sources_data:
        # Check if source already exists
        existing_source = session.execute(select(Source).where(Source.name == source_data["name"]))
        existing = existing_source.scalar_one_or_none()

        if existing:
            print(f"Source '{source_data['name']}' already exists, skipping...")
            continue

        # Create new source
        source = Source(**source_data)
        session.add(source)
        print(f"Added source: {source_data['name']}")

    # Commit all changes
    session.commit()
    print("Sources seeding completed successfully!")


def main() -> None:
    """Main function to run the seeding process."""
    print("Starting sources seeding process...")

    # Create engine and session
    engine = create_sync_engine()
    session_local = sessionmaker(bind=engine)

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Seed sources
    with session_local() as session:
        try:
            seed_sources(session)
        except Exception as e:
            print(f"Error during seeding: {e}")
            session.rollback()
            raise

    print("Seeding process completed!")


if __name__ == "__main__":
    main()
