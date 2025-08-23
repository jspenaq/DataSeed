"""
Sources API endpoints for DataSeed.

Provides endpoints for managing and monitoring data sources,
including source configuration, health status, and ingestion statistics.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.ingestion import IngestionRun
from app.models.source import Source
from app.schemas.source import (
    IngestionRunSummary,
    SourceDetailResponse,
    SourcesResponse,
    SourceStats,
    SourceWithStats,
)

router = APIRouter()


async def calculate_source_stats(db: AsyncSession, source_id: int, days: int = 7) -> SourceStats:
    """Calculate statistics for a source over the specified number of days."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get basic run counts
    total_runs_result = await db.execute(
        select(func.count(IngestionRun.id)).where(  # CORRECTED
            and_(IngestionRun.source_id == source_id, IngestionRun.started_at >= cutoff_date),
        ),
    )
    total_runs = total_runs_result.scalar() or 0

    successful_runs_result = await db.execute(
        select(func.count(IngestionRun.id)).where(  # CORRECTED
            and_(
                IngestionRun.source_id == source_id,
                IngestionRun.status == "completed",
                IngestionRun.started_at >= cutoff_date,
            ),
        ),
    )
    successful_runs = successful_runs_result.scalar() or 0

    failed_runs = total_runs - successful_runs
    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

    # Get item processing stats
    items_stats_result = await db.execute(
        select(func.sum(IngestionRun.items_processed)).where(  # CORRECTED
            and_(IngestionRun.source_id == source_id, IngestionRun.started_at >= cutoff_date),
        ),
    )
    total_items_processed = items_stats_result.scalar() or 0

    # Items in last 24 hours
    last_24h = datetime.utcnow() - timedelta(hours=24)
    items_24h_result = await db.execute(
        select(func.sum(IngestionRun.items_processed)).where(  # CORRECTED
            and_(IngestionRun.source_id == source_id, IngestionRun.started_at >= last_24h),
        ),
    )
    items_last_24h = items_24h_result.scalar() or 0

    avg_items_per_run = (total_items_processed / total_runs) if total_runs > 0 else 0.0

    # Get median duration for completed runs
    completed_runs = await db.execute(
        select(func.extract("epoch", IngestionRun.completed_at - IngestionRun.started_at)).where(  # CORRECTED
            and_(
                IngestionRun.source_id == source_id,
                IngestionRun.status == "completed",
                IngestionRun.completed_at.isnot(None),
                IngestionRun.started_at >= cutoff_date,
            ),
        ),
    )
    durations = [row[0] for row in completed_runs.fetchall() if row[0] is not None]
    median_duration_seconds = None
    if durations:
        durations.sort()
        n = len(durations)
        median_duration_seconds = durations[n // 2] if n % 2 == 1 else (durations[n // 2 - 1] + durations[n // 2]) / 2

    # Get last successful run
    last_successful_result = await db.execute(
        select(IngestionRun.completed_at)
        .where(  # CORRECTED
            and_(IngestionRun.source_id == source_id, IngestionRun.status == "completed"),
        )
        .order_by(desc(IngestionRun.completed_at))
        .limit(1),
    )
    last_successful_run = last_successful_result.scalar()

    # Get last run status
    last_run_result = await db.execute(
        select(IngestionRun.status)
        .where(IngestionRun.source_id == source_id)  # CORRECTED
        .order_by(desc(IngestionRun.started_at))
        .limit(1),
    )
    last_run_status = last_run_result.scalar()

    return SourceStats(
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        success_rate=success_rate,
        total_items_processed=total_items_processed,
        items_last_24h=items_last_24h,
        avg_items_per_run=avg_items_per_run,
        median_duration_seconds=median_duration_seconds,
        last_successful_run=last_successful_run,
        last_run_status=last_run_status,
    )


async def get_recent_runs(db: AsyncSession, source_id: int, limit: int = 10) -> list[IngestionRunSummary]:
    """Get recent ingestion runs for a source."""
    result = await db.execute(
        IngestionRun.__table__.select()
        .where(IngestionRun.source_id == source_id)
        .order_by(desc(IngestionRun.started_at))
        .limit(limit),
    )

    runs = []
    for row in result.fetchall():
        # Calculate duration if completed
        duration_seconds = None
        if row.completed_at and row.started_at:
            duration_seconds = (row.completed_at - row.started_at).total_seconds()

        runs.append(
            IngestionRunSummary(
                id=row.id,
                started_at=row.started_at,
                completed_at=row.completed_at,
                status=row.status,
                items_processed=row.items_processed,
                items_new=row.items_new,
                items_updated=row.items_updated,
                items_failed=row.items_failed,
                errors_count=row.errors_count,
                duration_seconds=duration_seconds,
                error_notes=row.error_notes,
            ),
        )

    return runs


def determine_source_health(stats: SourceStats) -> str:
    """Determine source health based on statistics."""
    if stats.total_runs == 0:
        return "unknown"

    # Check if last run was recent (within 2 hours)
    if stats.last_successful_run:
        # CORRECTED: Use timezone-aware datetime.now(timezone.utc)
        time_since_last = datetime.now(UTC) - stats.last_successful_run
        if time_since_last > timedelta(hours=2):
            return "degraded"

    # Check success rate
    if stats.success_rate >= 95:
        return "healthy"
    if stats.success_rate >= 80:
        return "degraded"
    return "failed"


@router.get("/", response_model=SourcesResponse)
async def get_sources(
    status: str | None = Query(None, description="Filter by health status (healthy, degraded, failed)"),
    search: str | None = Query(None, description="Search sources by name"),
    db: AsyncSession = Depends(get_db),
) -> SourcesResponse:
    """
    Get all data sources with their statistics and health information.

    Returns a list of sources with their current health status, recent statistics,
    and basic configuration information.
    """
    # Build query
    query = Source.__table__.select().where(Source.is_active)

    if search:
        query = query.where(Source.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    sources = result.fetchall()

    sources_with_stats = []
    health_counts = {"healthy": 0, "degraded": 0, "failed": 0, "unknown": 0}

    for source_row in sources:
        # Calculate stats for this source
        stats = await calculate_source_stats(db, source_row.id)
        recent_runs = await get_recent_runs(db, source_row.id, limit=5)

        # Determine health status
        health = determine_source_health(stats)
        health_counts[health] += 1

        # Create source with stats
        source_with_stats = SourceWithStats(
            id=source_row.id,
            name=source_row.name,
            type=source_row.type,
            base_url=source_row.base_url,
            rate_limit=source_row.rate_limit,
            config=source_row.config,
            is_active=source_row.is_active,
            created_at=source_row.created_at,
            updated_at=source_row.updated_at,
            stats=stats,
            recent_runs=recent_runs,
        )

        # Apply status filter
        if status is None or health == status:
            sources_with_stats.append(source_with_stats)

    return SourcesResponse(
        sources=sources_with_stats,
        total=len(sources),
        healthy=health_counts["healthy"],
        degraded=health_counts["degraded"],
        failed=health_counts["failed"],
    )


@router.get("/{source_id}", response_model=SourceDetailResponse)
async def get_source_details(
    source_id: int,
    runs_limit: int = Query(10, description="Number of recent runs to include"),
    db: AsyncSession = Depends(get_db),
) -> SourceDetailResponse:
    """
    Get detailed information for a specific source.

    Returns comprehensive source information including recent ingestion runs,
    detailed statistics, and trend data for visualization.
    """
    # Get source
    result = await db.execute(Source.__table__.select().where(Source.id == source_id))
    source_row = result.fetchone()

    if not source_row:
        raise HTTPException(status_code=404, detail="Source not found")

    # Calculate stats
    stats = await calculate_source_stats(db, source_id, days=30)  # 30 days for details
    recent_runs = await get_recent_runs(db, source_id, limit=runs_limit)

    # Get lag trend data for sparkline (last 24 hours)
    lag_trend_result = await db.execute(
        IngestionRun.__table__.select()
        .where(
            and_(
                IngestionRun.source_id == source_id,
                IngestionRun.status == "completed",
                IngestionRun.started_at >= datetime.utcnow() - timedelta(hours=24),
            ),
        )
        .order_by(IngestionRun.started_at),
    )

    lag_trend = []
    for run in lag_trend_result.fetchall():
        if run.completed_at and run.started_at:
            duration = (run.completed_at - run.started_at).total_seconds()
            lag_trend.append(
                {
                    "timestamp": run.started_at.isoformat(),
                    "duration_seconds": duration,
                    "items_processed": run.items_processed,
                },
            )

    source_with_stats = SourceWithStats(
        id=source_row.id,
        name=source_row.name,
        type=source_row.type,
        base_url=source_row.base_url,
        rate_limit=source_row.rate_limit,
        config=source_row.config,
        is_active=source_row.is_active,
        created_at=source_row.created_at,
        updated_at=source_row.updated_at,
        stats=stats,
        recent_runs=recent_runs[:5],  # Limit for summary
    )

    return SourceDetailResponse(source=source_with_stats, ingestion_runs=recent_runs, lag_trend=lag_trend)
