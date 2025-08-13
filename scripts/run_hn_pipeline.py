#!/usr/bin/env python3
"""
HackerNews ETL Pipeline Verification Script

This script demonstrates and verifies the complete ETL pipeline for HackerNews data.
"""

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
from app.core.extractors.hackernews import HackerNewsExtractor
from app.core.registry import get_normalizer
from app.core.services.ingestion import IngestionService
from app.models.source import Source


async def get_hackernews_source(db: AsyncSession) -> Source | None:
    """Fetch the HackerNews source from the database."""
    logger.info("Fetching HackerNews source from database...")
    stmt = select(Source).where(Source.name == "hackernews")
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if source:
        logger.info(f"Found HackerNews source: ID={source.id}, URL={source.base_url}")
    else:
        logger.error("HackerNews source not found in database!")
        logger.info("Please run 'python scripts/seed_sources.py' first")
    return source


async def run_hackernews_pipeline(db: AsyncSession):
    """Execute the complete HackerNews ETL pipeline."""
    logger.info("=" * 60)
    logger.info("Starting HackerNews ETL Pipeline Verification")
    logger.info("=" * 60)

    # Step 1: Get HackerNews source
    source = await get_hackernews_source(db)
    if not source:
        raise Exception("HackerNews source not found")

    # Step 2: Initialize components
    extractor_config = ExtractorConfig(base_url=source.base_url, rate_limit=source.rate_limit, config=source.config)
    extractor = HackerNewsExtractor(extractor_config)
    normalizer = get_normalizer(source.name, source.id)
    ingestion_service = IngestionService(db)

    # Step 3: Create and track ingestion run
    ingestion_run = await ingestion_service.create_ingestion_run(source.id)
    logger.info(f"Created ingestion run ID={ingestion_run.id}")

    try:
        # Step 4: Health check and data extraction
        if not await extractor.health_check():
            raise Exception("HackerNews API health check failed")
        logger.info("✓ HackerNews API is accessible")

        raw_items = await extractor.fetch_recent(limit=20)
        logger.info(f"✓ Extracted {len(raw_items)} raw items")

        # Step 5: Normalization
        normalized_items = [normalizer.normalize(item) for item in raw_items]
        logger.info(f"✓ Normalized {len(normalized_items)} items")

        # Step 6: Batch upsert
        upsert_stats = await ingestion_service.batch_upsert_items(normalized_items)
        logger.info(f"✓ Batch upsert completed: {upsert_stats['new']} new, {upsert_stats['updated']} updated")

        # Step 7: Complete ingestion run
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
    logger.info("HackerNews Pipeline Verification Script")
    logger.info(f"Database URL: {settings.DATABASE_URL}")

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await run_hackernews_pipeline(session)
        logger.info("✅ Pipeline verification completed successfully!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Pipeline verification failed: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
