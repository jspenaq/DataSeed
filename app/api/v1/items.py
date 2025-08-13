from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.items import ContentItem
from app.models.source import Source
from app.schemas.items import ContentItemResponse, PaginatedContentItems

router = APIRouter()


@router.get("/", response_model=PaginatedContentItems)
async def get_items(
    source_name: str | None = Query(None, description="Filter by source name"),
    q: str | None = Query(None, description="Search query for item titles"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Offset from the start"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedContentItems:
    """
    Fetch and paginate content items from the database.

    Args:
        source_name: Optional filter by source name (e.g., 'hackernews', 'reddit')
        q: Optional search query for item titles
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

    # Apply search filter if provided
    if q:
        query = query.where(func.lower(ContentItem.title).contains(q.lower()))

    # Order by published_at descending (most recent first), with id as tie-breaker
    query = query.order_by(ContentItem.published_at.desc(), ContentItem.id.desc())

    # Build explicit count query that matches the main query structure
    count_query = select(func.count(ContentItem.id))
    if source_name:
        count_query = count_query.select_from(ContentItem).join(Source).where(Source.name == source_name)
    else:
        count_query = count_query.select_from(ContentItem)

    # If the q (search query) parameter is present, add the where clause to the count query as well
    if q:
        count_query = count_query.where(func.lower(ContentItem.title).contains(q.lower()))

    total_items = (await db.execute(count_query)).scalar_one()

    # Apply pagination
    paginated_query = query.offset(offset).limit(limit)

    # Execute the query
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    # Convert to response schemas
    item_responses = [ContentItemResponse.model_validate(item) for item in items]

    return PaginatedContentItems(
        total=total_items,
        limit=limit,
        offset=offset,
        items=item_responses,
    )
