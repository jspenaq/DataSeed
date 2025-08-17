"""
Source schemas for API serialization and validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    """Base source schema with common fields."""

    name: str = Field(..., description="Source name (e.g., 'hackernews', 'reddit')")
    type: str = Field(..., description="Source type (e.g., 'api', 'scraping')")
    base_url: str = Field(..., description="Base URL for the source API")
    rate_limit: int = Field(default=60, description="Rate limit in requests per minute")
    config: dict[str, Any] = Field(default_factory=dict, description="Source-specific configuration")
    is_active: bool = Field(default=True, description="Whether the source is active")


class SourceCreate(SourceBase):
    """Schema for creating a new source."""

    pass


class SourceUpdate(BaseModel):
    """Schema for updating an existing source."""

    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    rate_limit: int | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class IngestionRunSummary(BaseModel):
    """Summary of an ingestion run for source details."""

    id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    items_processed: int
    items_new: int
    items_updated: int
    items_failed: int
    errors_count: int
    duration_seconds: float | None
    error_notes: str | None

    class Config:
        from_attributes = True


class SourceStats(BaseModel):
    """Statistics for a source."""

    total_runs: int = Field(description="Total number of ingestion runs")
    successful_runs: int = Field(description="Number of successful runs")
    failed_runs: int = Field(description="Number of failed runs")
    success_rate: float = Field(description="Success rate as percentage")
    total_items_processed: int = Field(description="Total items processed")
    items_last_24h: int = Field(description="Items processed in last 24 hours")
    avg_items_per_run: float = Field(description="Average items per run")
    median_duration_seconds: float | None = Field(description="Median run duration in seconds")
    last_successful_run: datetime | None = Field(description="Timestamp of last successful run")
    last_run_status: str | None = Field(description="Status of the most recent run")


class SourceWithStats(SourceBase):
    """Source with statistics and health information."""

    id: int
    created_at: datetime
    updated_at: datetime
    stats: SourceStats
    recent_runs: list[IngestionRunSummary] = Field(default_factory=list, description="Recent ingestion runs")

    class Config:
        from_attributes = True


class Source(SourceBase):
    """Complete source schema for API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourcesResponse(BaseModel):
    """Response schema for sources list endpoint."""

    sources: list[SourceWithStats]
    total: int
    healthy: int
    degraded: int
    failed: int


class SourceDetailResponse(BaseModel):
    """Response schema for individual source details."""

    source: SourceWithStats
    ingestion_runs: list[IngestionRunSummary]
    lag_trend: list[dict[str, Any]] = Field(description="Ingestion lag trend data for sparkline")
