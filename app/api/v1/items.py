from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.items import ContentItem
from app.models.source import Source
from app.schemas.items import ContentItemResponse, PaginatedContentItems

router = APIRouter()


@router.get("/", response_model=PaginatedContentItems)
async def get_items(
    source_name: Optional[str] = Query(None, description="Filter by source name"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Offset from the start"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedContentItems:
    """
    Fetch and paginate content items from the database.
    
    Args:
        source_name: Optional filter by source name (e.g., 'hackernews', 'reddit')
        limit: Number of items to return (1-100)
        offset: Number of items to skip
        db: Database session dependency
        
    Returns:
        PaginatedItemsResponse with items and pagination metadata
    """
    # Build the base query
    query = select(ContentItem).options(selectinload(ContentItem.source))
    
    # Apply source filter if provided
    if source_name:
        query = query.join(Source).where(Source.name == source_name)
    
    # Order by published_at descending (most recent first)
    query = query.order_by(ContentItem.published_at.desc())
    
    # Get total count for pagination
    count_query = select(func.count(ContentItem.id))
    if source_name:
        count_query = count_query.select_from(ContentItem).join(Source).where(Source.name == source_name)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    paginated_query = query.offset(offset).limit(limit)
    
    # Execute the query
    result = await db.execute(paginated_query)
    items = result.scalars().all()
    
    # Convert to response schemas
    item_responses = [ContentItemResponse.model_validate(item) for item in items]
    
    return PaginatedContentItems(
        total=total,
        limit=limit,
        offset=offset,
        items=item_responses,
    )