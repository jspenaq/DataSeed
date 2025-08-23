from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.caching import CacheInfo, cache_dependency, set_cache_headers
from app.api.deps import get_db
from app.core.pagination import decode_cursor, encode_cursor
from app.models.items import ContentItem
from app.models.source import Source
from app.schemas.items import ContentItemCursorPage, ContentItemResponse, ItemsStats, PaginatedContentItems, SourceStat

router = APIRouter()


@router.get(
    "/",
    response_model=PaginatedContentItems,
    summary="Get content items with offset pagination",
    description="Retrieve content items using traditional offset/limit pagination. "
    "Results are ordered by publication date (newest first). "
    "Supports filtering by source and full-text search across titles and content.",
)
async def get_items(
    response: Response,
    source_name: str | None = Query(
        None,
        description="Filter by source name (e.g., 'hackernews', 'reddit', 'github', 'producthunt')",
        examples=["hackernews"],
    ),
    q: str | None = Query(
        None,
        description="Search query that matches against both item titles and content using case-insensitive "
        "partial matching",
        examples=["artificial intelligence"],
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page", examples=[20]),
    offset: int = Query(
        0,
        ge=0,
        description="Number of items to skip from the beginning (for pagination)",
        examples=[0],
    ),
    db: AsyncSession = Depends(get_db),
    cache_info: CacheInfo = Depends(cache_dependency),
) -> PaginatedContentItems:
    """
    Fetch and paginate content items from the database using offset/limit pagination.

    This endpoint uses traditional offset/limit pagination where you specify how many items
    to skip (offset) and how many to return (limit). For large datasets or better performance,
    consider using the cursor-based pagination endpoint instead.

    Args:
        source_name: Optional filter by source name (e.g., 'hackernews', 'reddit')
        q: Optional search query for item titles and content
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
        query = query.where(or_(ContentItem.title.ilike(f"%{q}%"), ContentItem.content.ilike(f"%{q}%")))

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
        count_query = count_query.where(or_(ContentItem.title.ilike(f"%{q}%"), ContentItem.content.ilike(f"%{q}%")))

    total_items = (await db.execute(count_query)).scalar_one()

    # Apply pagination
    paginated_query = query.offset(offset).limit(limit)

    # Execute the query
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    # Convert to response schemas
    item_responses = [ContentItemResponse.model_validate(item) for item in items]

    # Set cache headers
    set_cache_headers(response, cache_info)

    return PaginatedContentItems(
        total=total_items,
        limit=limit,
        offset=offset,
        items=item_responses,
    )


@router.get(
    "/cursor",
    response_model=ContentItemCursorPage,
    summary="Get content items with cursor pagination",
    description="Retrieve content items using cursor-based pagination for better performance with large datasets. "
    "The cursor encodes the position in the result set and provides consistent pagination even when new "
    "items are added.",
)
async def get_items_cursor(
    response: Response,
    source_name: str | None = Query(
        None,
        description="Filter by source name (e.g., 'hackernews', 'reddit', 'github', 'producthunt')",
        examples=["hackernews"],
    ),
    q: str | None = Query(
        None,
        description="Search query that matches against both item titles and content using case-insensitive "
        "partial matching",
        examples=["machine learning"],
    ),
    cursor: str | None = Query(
        None,
        description="Base64-encoded cursor for pagination. Use the 'next_cursor' from previous response "
        "to get the next page",
        examples=["MjAyNC0wMS0xNVQxMDozMDowMFo6MTIzNDU="],
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page", examples=[20]),
    db: AsyncSession = Depends(get_db),
    cache_info: CacheInfo = Depends(cache_dependency),
) -> ContentItemCursorPage:
    """
    Fetch content items using cursor-based pagination.

    Cursor-based pagination provides better performance and consistency compared to offset-based pagination,
    especially for large datasets. The cursor encodes the published_at timestamp and item ID to maintain
    a stable position in the result set even when new items are added.

    The cursor format is a base64-encoded string containing the timestamp and ID of the last item from
    the previous page. Use the 'next_cursor' field from the response to fetch the next page.

    Args:
        source_name: Optional filter by source name (e.g., 'hackernews', 'reddit')
        q: Optional search query for item titles and content
        cursor: Optional base64-encoded cursor for pagination
        limit: Number of items to return (1-100)
        db: Database session dependency

    Returns:
        ContentItemCursorPage with items and next cursor for pagination
    """
    # Build the base query
    query = select(ContentItem).options(selectinload(ContentItem.source))

    # Apply source filter if provided
    if source_name:
        query = query.join(Source).where(Source.name == source_name)

    # Apply search filter if provided
    if q:
        query = query.where(or_(ContentItem.title.ilike(f"%{q}%"), ContentItem.content.ilike(f"%{q}%")))

    # Apply cursor filter if provided
    if cursor:
        try:
            cursor_published_at, cursor_id = decode_cursor(cursor)
            # Cursor logic: WHERE (published_at < cursor_published_at) OR
            # (published_at = cursor_published_at AND id < cursor_id)
            query = query.where(
                or_(
                    ContentItem.published_at < cursor_published_at,
                    and_(ContentItem.published_at == cursor_published_at, ContentItem.id < cursor_id),
                ),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid cursor: {e}") from e

    # Order by published_at descending (most recent first), with id as tie-breaker
    query = query.order_by(ContentItem.published_at.desc(), ContentItem.id.desc())

    # Fetch limit + 1 items to determine if there's a next page
    paginated_query = query.limit(limit + 1)

    # Execute the query
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    # Determine if there's a next page and generate next cursor
    next_cursor = None
    if len(items) > limit:
        # Remove the extra item and use it to generate the next cursor
        items = items[:limit]
        last_item = items[-1]
        next_cursor = encode_cursor(last_item.published_at, last_item.id)

    # Convert to response schemas
    item_responses = [ContentItemResponse.model_validate(item) for item in items]

    # Set cache headers
    set_cache_headers(response, cache_info)

    return ContentItemCursorPage(
        limit=limit,
        next_cursor=next_cursor,
        items=item_responses,
    )


def _parse_window(window: str) -> timedelta:
    """Parse window string to timedelta."""
    if window.endswith("h"):
        hours = int(window[:-1])
        return timedelta(hours=hours)
    if window.endswith("d"):
        days = int(window[:-1])
        return timedelta(days=days)
    if window.endswith("w"):
        weeks = int(window[:-1])
        return timedelta(weeks=weeks)
    raise ValueError(f"Invalid window format: {window}. Use format like '24h', '7d', '1w'")


@router.get(
    "/stats",
    response_model=ItemsStats,
    summary="Get content items statistics",
    description="Retrieve comprehensive statistics about content items including totals, recent activity, "
    "top sources by volume, and score analytics. Useful for dashboard analytics and monitoring.",
)
async def get_items_stats(
    response: Response,
    window: str = Query(
        "24h",
        description="Time window for counting new items. Format: number + unit (h=hours, d=days, w=weeks)",
        examples=["24h"],
    ),
    source_name: str | None = Query(
        None,
        description="Filter statistics by specific source name",
        examples=["hackernews"],
    ),
    db: AsyncSession = Depends(get_db),
    cache_info: CacheInfo = Depends(cache_dependency),
) -> ItemsStats:
    """
    Get comprehensive statistics about content items.

    Returns various statistics including total item counts, new items within the specified time window,
    top sources ranked by item count, and score statistics (max and average scores).

    The window parameter accepts formats like:
    - '24h' for 24 hours
    - '7d' for 7 days
    - '1w' for 1 week
    - '30d' for 30 days

    Args:
        window: Time window for counting new items (e.g., '24h', '7d', '1w')
        source_name: Optional filter by source name
        db: Database session dependency

    Returns:
        ItemsStats containing total items, new items in window, top sources, and score statistics
    """
    try:
        window_delta = _parse_window(window)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    window_start = datetime.utcnow() - window_delta

    # Base query for filtering
    base_query = select(ContentItem)
    if source_name:
        base_query = base_query.join(Source).where(Source.name == source_name)

    # Total items count
    total_query = select(func.count(ContentItem.id))
    if source_name:
        total_query = total_query.select_from(ContentItem).join(Source).where(Source.name == source_name)
    else:
        total_query = total_query.select_from(ContentItem)

    total_items = (await db.execute(total_query)).scalar_one()

    # New items in window count
    new_query = select(func.count(ContentItem.id)).select_from(ContentItem)
    if source_name:
        new_query = new_query.join(Source).where(
            and_(Source.name == source_name, ContentItem.created_at >= window_start),
        )
    else:
        new_query = new_query.where(ContentItem.created_at >= window_start)

    new_last_window = (await db.execute(new_query)).scalar_one()

    # Top sources by item count
    sources_query = (
        select(Source.name, func.count(ContentItem.id).label("item_count")).select_from(ContentItem).join(Source)
    )
    if source_name:
        sources_query = sources_query.where(Source.name == source_name)

    sources_query = sources_query.group_by(Source.name).order_by(func.count(ContentItem.id).desc()).limit(10)

    sources_result = await db.execute(sources_query)
    top_sources = [SourceStat(source_name=row.name, item_count=row.item_count) for row in sources_result]

    # Score statistics
    score_query = select(func.max(ContentItem.score), func.avg(ContentItem.score)).select_from(ContentItem)
    if source_name:
        score_query = score_query.join(Source).where(Source.name == source_name)

    score_result = await db.execute(score_query)
    max_score, avg_score = score_result.one()

    # Set cache headers
    set_cache_headers(response, cache_info)

    return ItemsStats(
        total_items=total_items,
        new_last_window=new_last_window,
        top_sources=top_sources,
        max_score=float(max_score) if max_score is not None else None,
        avg_score=float(avg_score) if avg_score is not None else None,
    )


@router.get(
    "/trending",
    response_model=list[ContentItemResponse],
    summary="Get trending content items",
    description="Retrieve trending content items within a specified time window, ranked by score and recency. "
    "Supports both simple score-based ranking and advanced 'hot score' algorithm for better trend detection.",
)
async def get_trending_items(
    response: Response,
    window: str = Query(
        "24h",
        description="Time window for trending analysis. Format: number + unit (h=hours, d=days, w=weeks)",
        examples=["24h"],
    ),
    source_name: str | None = Query(
        None,
        description="Filter trending items by specific source name",
        examples=["hackernews"],
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of trending items to return", examples=[20]),
    use_hot_score: bool = Query(
        False,
        description="Enable advanced hot score algorithm that balances item score with recency "
        "(PostgreSQL only, falls back to simple scoring on other databases)",
        examples=[False],
    ),
    db: AsyncSession = Depends(get_db),
    cache_info: CacheInfo = Depends(cache_dependency),
) -> list[ContentItemResponse]:
    """
    Get trending content items within a specified time window.

    This endpoint identifies trending content by analyzing items within the specified time window
    and ranking them by score and recency. Two ranking algorithms are available:

    1. **Simple Ranking** (default): Orders by score DESC, then published_at DESC
    2. **Hot Score Algorithm** (use_hot_score=true): Uses a logarithmic formula that balances
       high scores with recency: ln(score + 1) + (published_at_epoch / 43200)

    The hot score algorithm gives more weight to recent items with high engagement, similar to
    algorithms used by Reddit and Hacker News for their "hot" rankings.

    Window format examples:
    - '1h' for last hour
    - '24h' for last 24 hours
    - '7d' for last 7 days
    - '1w' for last week

    Args:
        window: Time window for trending items (e.g., '24h', '7d', '1w')
        source_name: Optional filter by source name
        limit: Number of items to return (1-100)
        use_hot_score: Whether to use hot score algorithm for better trend detection
        db: Database session dependency

    Returns:
        List of trending ContentItemResponse objects ordered by relevance
    """
    try:
        window_delta = _parse_window(window)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    window_start = datetime.utcnow() - window_delta

    # Build the base query
    query = select(ContentItem).options(selectinload(ContentItem.source))

    # Apply source filter if provided
    if source_name:
        query = query.join(Source).where(Source.name == source_name)

    # Filter items within the time window
    query = query.where(ContentItem.published_at >= window_start)

    # Apply sorting logic
    if use_hot_score:
        # Hot score algorithm for PostgreSQL: ln(score + 1) + (published_at_epoch / 43200)
        # This gives more weight to recent items with high scores
        try:
            hot_score = func.ln(func.coalesce(ContentItem.score, 0) + 1) + (
                func.extract("epoch", ContentItem.published_at) / 43200
            )
            query = query.order_by(hot_score.desc(), ContentItem.published_at.desc())
        except Exception:
            # Fallback to primary sorting if hot score fails (e.g., SQLite)
            query = query.order_by(func.coalesce(ContentItem.score, 0).desc(), ContentItem.published_at.desc())
    else:
        # Primary sorting: score DESC, published_at DESC
        query = query.order_by(func.coalesce(ContentItem.score, 0).desc(), ContentItem.published_at.desc())

    # Apply limit
    query = query.limit(limit)

    # Execute the query
    result = await db.execute(query)
    items = result.scalars().all()

    # Set cache headers
    set_cache_headers(response, cache_info)

    # Convert to response schemas
    return [ContentItemResponse.model_validate(item) for item in items]
