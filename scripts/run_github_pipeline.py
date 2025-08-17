#!/usr/bin/env python3
"""
GitHub ETL Pipeline Verification Script

This script demonstrates and verifies the complete ETL pipeline for GitHub data.

Note: GitHub's search API requires authentication for most queries. To get actual data:
1. Create a GitHub Personal Access Token at https://github.com/settings/tokens
2. Set the GITHUB_TOKEN environment variable: export GITHUB_TOKEN=your_token_here
3. Run the script again

Without authentication, the script will complete successfully but extract 0 items
due to GitHub API rate limiting for unauthenticated requests.
"""

# Load environment variables from .env if present (at the very top)
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
except ImportError:
    pass


import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.extractors.base import ExtractorConfig
from app.core.extractors.github import GitHubExtractor
from app.core.services.ingestion import IngestionService
from app.models.source import Source


async def get_github_source(db: AsyncSession) -> Source | None:
    """Fetch the GitHub source from the database."""
    logger.info("Fetching GitHub source from database...")
    stmt = select(Source).where(Source.name == "github")
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if source:
        logger.info(f"Found GitHub source: ID={source.id}, URL={source.base_url}")
    else:
        logger.error("GitHub source not found in database!")
        logger.info("Please run 'python scripts/seed_sources.py' first")
    return source


async def run_github_pipeline(db: AsyncSession):
    """Execute the complete GitHub ETL pipeline."""
    logger.info("=" * 60)
    logger.info("Starting GitHub ETL Pipeline Verification")
    logger.info("=" * 60)

    # Step 1: Get GitHub source
    source = await get_github_source(db)
    if not source:
        raise Exception("GitHub source not found")

    # Step 2: Initialize components with environment variable substitution
    config = source.config.copy()
    # Handle environment variable substitution for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        config["token"] = github_token
        logger.info("Using GitHub token from environment variable")
    elif config.get("token") == "${GITHUB_TOKEN}":
        config["token"] = None
        logger.warning("GITHUB_TOKEN environment variable not set")

    extractor_config = ExtractorConfig(base_url=source.base_url, rate_limit=source.rate_limit, config=config)
    extractor = GitHubExtractor(extractor_config, source_id=source.id)
    ingestion_service = IngestionService(db)

    # Step 3: Create and track ingestion run
    ingestion_run = await ingestion_service.create_ingestion_run(source.id)
    logger.info(f"Created ingestion run ID={ingestion_run.id}")

    try:
        # Step 4: Health check and data extraction
        if extractor.token:
            logger.info("GitHub token configured: Yes")
            try:
                if not await extractor.health_check():
                    logger.warning("⚠ GitHub API health check failed, but continuing with data extraction")
                else:
                    logger.info("✓ GitHub API is accessible")
            except Exception as e:
                logger.warning(f"⚠ Health check failed: {e}, but continuing with data extraction")
        else:
            logger.warning("⚠ No GitHub token provided, skipping health check")
            logger.info("Note: GitHub API has rate limits for unauthenticated requests (60 requests/hour)")

        # Note: GitHubExtractor.fetch_recent() returns already normalized items
        logger.info("Attempting to fetch GitHub data...")
        normalized_items = await extractor.fetch_recent(limit=15)  # Reduced limit for testing
        logger.info(f"✓ Extracted and normalized {len(normalized_items)} items")

        # Step 5: Batch upsert (items are already normalized)
        upsert_stats = await ingestion_service.batch_upsert_items(normalized_items)
        logger.info(f"✓ Batch upsert completed: {upsert_stats['new']} new, {upsert_stats['updated']} updated")

        # Step 6: Complete ingestion run
        await ingestion_service.complete_ingestion_run(ingestion_run.id, upsert_stats)
        logger.info("✓ Ingestion run completed successfully")
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await ingestion_service.update_ingestion_run(ingestion_run.id, status="failed", error_notes=str(e))
        raise
    finally:
        await extractor.close()


async def main():
    """Main entry point for the script."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.info("GitHub Pipeline Verification Script")
    logger.info(f"Database URL: {settings.DATABASE_URL}")

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await run_github_pipeline(session)
        logger.info("✅ Pipeline verification completed successfully!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Pipeline verification failed: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
