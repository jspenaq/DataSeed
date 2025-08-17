from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import CursorPage
from app.schemas.source import SourceInfo


class ContentItemBase(BaseModel):
    """Base schema for ContentItem with common fields."""

    external_id: str = Field(description="Source's unique identifier for the item")
    title: str = Field(description="Normalized title text")
    content: str | None = Field(default=None, description="Main text content/description")
    url: str = Field(description="Original URL of the item")
    score: int | None = Field(default=None, description="Upvotes/likes/stars")
    published_at: datetime = Field(description="When the item was originally published")


class ContentItemCreate(ContentItemBase):
    """Schema for creating a new ContentItem."""

    source_id: int = Field(description="Reference to the data source")


class ContentItemResponse(ContentItemBase):
    """Schema for ContentItem API responses."""

    id: int = Field(description="Internal database ID")
    # source_id: int = Field(description="Reference to the data source")
    source: SourceInfo = Field(description="The source of the content item")
    created_at: datetime = Field(description="When the item was created in our system")
    updated_at: datetime = Field(description="When the item was last updated in our system")

    class Config:
        from_attributes = True


class ContentItemUpdate(BaseModel):
    """Schema for updating a ContentItem."""

    title: str | None = None
    content: str | None = None
    url: str | None = None
    score: int | None = None
    published_at: datetime | None = None


class PaginatedContentItems(BaseModel):
    """Schema for paginated ContentItem responses."""

    total: int = Field(description="Total number of items")
    limit: int = Field(description="Number of items per page")
    offset: int = Field(description="Offset from the start")
    items: list[ContentItemResponse] = Field(description="List of content items")


class ContentItemCursorPage(CursorPage[ContentItemResponse]):
    """Schema for cursor-based paginated ContentItem responses."""

    pass


class SourceStat(BaseModel):
    """Schema for source statistics."""

    source_name: str = Field(description="Name of the data source")
    item_count: int = Field(description="Number of items from this source")


class ItemsStats(BaseModel):
    """Schema for items statistics response."""

    total_items: int = Field(description="Total number of items")
    new_last_window: int = Field(description="Number of items created within the specified window")
    top_sources: list[SourceStat] = Field(description="Top sources by item count")
    max_score: float | None = Field(default=None, description="Maximum score among items")
    avg_score: float | None = Field(default=None, description="Average score among items")
