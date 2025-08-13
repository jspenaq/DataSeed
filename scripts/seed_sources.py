#!/usr/bin/env python3
"""
Seed script to populate the sources table with initial data from YAML configuration.

This script reads source definitions from config/sources.yaml and creates the data sources
(HackerNews, Reddit, GitHub, ProductHunt) with their proper API endpoints and rate limits.
It's idempotent and can be run multiple times safely.
"""

import sys
from pathlib import Path
from typing import Any

import yaml

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


def load_sources_from_yaml() -> list[dict[str, Any]]:
    """Load sources data from the YAML configuration file."""
    # Construct the path to the YAML file relative to the script
    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path) as f:
        sources_data = yaml.safe_load(f)

    # Extract the sources list from the YAML structure
    sources_list = sources_data.get("sources", [])

    # Add is_active=True to each source since it's not in the YAML but needed for the database
    for source in sources_list:
        source["is_active"] = True

    return sources_list


def seed_sources(session: Session) -> None:
    """
    Seed the sources table with initial data from YAML configuration.

    Args:
        session: SQLAlchemy session
    """
    sources_data = load_sources_from_yaml()

    print(f"Seeding {len(sources_data)} sources from YAML configuration...")

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
    print("Starting sources seeding process from YAML configuration...")

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
