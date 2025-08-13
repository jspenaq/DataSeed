from datetime import datetime
from typing import Any, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class HealthCheckResult(BaseModel):
    """Schema for individual component health check result."""

    status: Literal["healthy", "unhealthy"] = Field(description="Status of the component")
    details: dict[str, Any] | None = Field(default=None, description="Additional details about the component health")
    error: str | None = Field(default=None, description="Error message if the component is unhealthy")


class HealthResponse(BaseModel):
    """Schema for the health check response."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(description="Overall status of the service")
    timestamp: datetime = Field(description="Time when the health check was performed")
    version: str | None = Field(default=None, description="Service version")
    checks: dict[str, HealthCheckResult] = Field(description="Health check results for individual components")


class PaginatedResponse(BaseModel):
    """Base schema for paginated responses."""

    total: int = Field(description="Total number of items")
    limit: int = Field(description="Number of items per page")
    offset: int = Field(description="Offset from the start")
    items: list[Any] = Field(description="List of items")


class CursorPage(BaseModel, Generic[T]):
    """Generic schema for cursor-based paginated responses."""

    limit: int = Field(description="Number of items per page")
    next_cursor: Optional[str] = Field(default=None, description="Cursor for the next page")
    items: List[T] = Field(description="List of items")
