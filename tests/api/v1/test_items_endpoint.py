"""
Tests for the /v1/items API endpoint.

Tests cover successful responses, pagination, filtering, and response schema validation.
"""

from datetime import datetime, timezone, timedelta
from typing import Generator
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.items import ContentItem
from app.models.source import Source


class TestItemsEndpoint:
    """Test cases for the /v1/items endpoint."""

    @pytest_asyncio.fixture
    async def test_sources(self, db_session: AsyncSession) -> list[Source]:
        """Create test sources for the items endpoint tests."""
        sources = [
            Source(
                name=f"hackernews_{uuid.uuid4().hex[:8]}",
                type="api",
                base_url="https://hacker-news.firebaseio.com/v0",
                rate_limit=600,
                config={"test": True},
                is_active=True,
            ),
            Source(
                name=f"reddit_{uuid.uuid4().hex[:8]}",
                type="api", 
                base_url="https://oauth.reddit.com",
                rate_limit=60,
                config={"test": True},
                is_active=True,
            ),
        ]
        
        for source in sources:
            db_session.add(source)
        await db_session.commit()
        
        for source in sources:
            await db_session.refresh(source)
        
        return sources

    @pytest_asyncio.fixture
    async def test_items(self, db_session: AsyncSession, test_sources: list[Source]) -> list[ContentItem]:
        """Create test content items for the endpoint tests."""
        base_time = datetime.now(timezone.utc)
        
        items = [
            # HackerNews items
            ContentItem(
                source_id=test_sources[0].id,
                external_id="hn_item_1",
                title="AI Breakthrough in Machine Learning",
                content="A new breakthrough in AI has been announced by researchers.",
                url="https://example.com/ai-breakthrough",
                score=250,
                published_at=base_time - timedelta(hours=1),
            ),
            ContentItem(
                source_id=test_sources[0].id,
                external_id="hn_item_2", 
                title="Python 3.12 Released",
                content="The latest version of Python brings new features and improvements.",
                url="https://example.com/python-312",
                score=180,
                published_at=base_time - timedelta(hours=2),
            ),
            ContentItem(
                source_id=test_sources[0].id,
                external_id="hn_item_3",
                title="Docker Best Practices",
                content="Learn the best practices for using Docker in production.",
                url="https://example.com/docker-practices",
                score=95,
                published_at=base_time - timedelta(hours=3),
            ),
            # Reddit items
            ContentItem(
                source_id=test_sources[1].id,
                external_id="reddit_item_1",
                title="Programming Tips for Beginners",
                content="Essential tips for new programmers starting their journey.",
                url="https://reddit.com/r/programming/tips",
                score=420,
                published_at=base_time - timedelta(minutes=30),
            ),
            ContentItem(
                source_id=test_sources[1].id,
                external_id="reddit_item_2",
                title="Web Development Trends 2024",
                content="The latest trends in web development for this year.",
                url="https://reddit.com/r/webdev/trends",
                score=310,
                published_at=base_time - timedelta(hours=4),
            ),
        ]
        
        for item in items:
            db_session.add(item)
        await db_session.commit()
        
        for item in items:
            await db_session.refresh(item)
            
        return items

    @pytest.fixture
    def client(self, db_session: AsyncSession) -> Generator[TestClient, None, None]:
        """Create a test client with database dependency override."""
        from app.api.deps import get_db
        
        async def override_get_db():
            yield db_session
            
        app.dependency_overrides[get_db] = override_get_db
        
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_get_items_success(self, client: TestClient, test_items: list[ContentItem]):
        """Test successful retrieval of items with 200 OK response."""
        response = client.get("/api/v1/items/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches PaginatedContentItems schema
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "items" in data
        
        # Verify pagination metadata
        assert data["total"] == 5  # Total items created in fixture
        assert data["limit"] == 20  # Default limit
        assert data["offset"] == 0  # Default offset
        assert len(data["items"]) == 5  # All items returned
        
        # Verify items are ordered by published_at descending (most recent first)
        items = data["items"]
        for i in range(len(items) - 1):
            current_time = datetime.fromisoformat(items[i]["published_at"].replace("Z", "+00:00"))
            next_time = datetime.fromisoformat(items[i + 1]["published_at"].replace("Z", "+00:00"))
            assert current_time >= next_time, "Items should be ordered by published_at descending"

    def test_get_items_pagination_limit(self, client: TestClient, test_items: list[ContentItem]):
        """Test pagination with custom limit parameter."""
        response = client.get("/api/v1/items/?limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert len(data["items"]) == 2

    def test_get_items_pagination_offset(self, client: TestClient, test_items: list[ContentItem]):
        """Test pagination with offset parameter."""
        response = client.get("/api/v1/items/?limit=2&offset=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 2
        assert len(data["items"]) == 2

    def test_get_items_pagination_beyond_total(self, client: TestClient, test_items: list[ContentItem]):
        """Test pagination when offset is beyond total items."""
        response = client.get("/api/v1/items/?offset=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert data["offset"] == 10
        assert len(data["items"]) == 0  # No items beyond total

    def test_get_items_filter_by_source_name(self, client: TestClient, test_items: list[ContentItem], test_sources: list[Source]):
        """Test filtering items by source_name parameter."""
        # Get the actual source name from the first test source
        hackernews_source_name = test_sources[0].name
        
        response = client.get(f"/api/v1/items/?source_name={hackernews_source_name}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return items from HackerNews source (3 items)
        assert data["total"] == 3
        assert len(data["items"]) == 3
        
        # Verify all returned items are from the correct source
        for item in data["items"]:
            assert item["source_id"] == test_sources[0].id

    def test_get_items_filter_by_nonexistent_source(self, client: TestClient, test_items: list[ContentItem]):
        """Test filtering by a source that doesn't exist."""
        response = client.get("/api/v1/items/?source_name=nonexistent_source")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_get_items_combined_filters_and_pagination(self, client: TestClient, test_items: list[ContentItem], test_sources: list[Source]):
        """Test combining source filtering with pagination."""
        hackernews_source_name = test_sources[0].name
        
        response = client.get(f"/api/v1/items/?source_name={hackernews_source_name}&limit=2&offset=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3  # Total HackerNews items
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert len(data["items"]) == 2  # 2 items returned (skipping first)

    def test_get_items_response_schema_structure(self, client: TestClient, test_items: list[ContentItem]):
        """Test that response structure matches ContentItemResponse schema."""
        response = client.get("/api/v1/items/?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 1
        item = data["items"][0]
        
        # Verify all required fields are present
        required_fields = [
            "id", "source_id", "external_id", "title", "content", 
            "url", "score", "published_at", "created_at", "updated_at"
        ]
        
        for field in required_fields:
            assert field in item, f"Field '{field}' missing from response"
        
        # Verify field types
        assert isinstance(item["id"], int)
        assert isinstance(item["source_id"], int)
        assert isinstance(item["external_id"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["url"], str)
        assert item["content"] is None or isinstance(item["content"], str)
        assert item["score"] is None or isinstance(item["score"], int)
        
        # Verify datetime fields are properly formatted
        for datetime_field in ["published_at", "created_at", "updated_at"]:
            assert isinstance(item[datetime_field], str)
            # Should be able to parse as ISO datetime
            datetime.fromisoformat(item[datetime_field].replace("Z", "+00:00"))

    def test_get_items_limit_validation(self, client: TestClient, test_items: list[ContentItem]):
        """Test limit parameter validation (1-100 range)."""
        # Test minimum limit
        response = client.get("/api/v1/items/?limit=1")
        assert response.status_code == 200
        
        # Test maximum limit
        response = client.get("/api/v1/items/?limit=100")
        assert response.status_code == 200
        
        # Test below minimum limit
        response = client.get("/api/v1/items/?limit=0")
        assert response.status_code == 422  # Validation error
        
        # Test above maximum limit
        response = client.get("/api/v1/items/?limit=101")
        assert response.status_code == 422  # Validation error

    def test_get_items_offset_validation(self, client: TestClient, test_items: list[ContentItem]):
        """Test offset parameter validation (>= 0)."""
        # Test valid offset
        response = client.get("/api/v1/items/?offset=0")
        assert response.status_code == 200
        
        response = client.get("/api/v1/items/?offset=5")
        assert response.status_code == 200
        
        # Test negative offset
        response = client.get("/api/v1/items/?offset=-1")
        assert response.status_code == 422  # Validation error

    def test_get_items_empty_database(self, client: TestClient, db_session: AsyncSession):
        """Test endpoint behavior when no items exist in database."""
        # This test uses a fresh client without test_items fixture
        response = client.get("/api/v1/items/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_get_items_with_null_content_and_score(self, client: TestClient, db_session: AsyncSession, test_sources: list[Source]):
        """Test items with null content and score fields."""
        # Create item with null content and score
        item = ContentItem(
            source_id=test_sources[0].id,
            external_id="null_fields_test",
            title="Item with Null Fields",
            content=None,  # Null content
            url="https://example.com/null-test",
            score=None,  # Null score
            published_at=datetime.now(timezone.utc),
        )
        
        db_session.add(item)
        await db_session.commit()
        
        response = client.get("/api/v1/items/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Find our test item
        test_item = None
        for item_data in data["items"]:
            if item_data["external_id"] == "null_fields_test":
                test_item = item_data
                break
        
        assert test_item is not None
        assert test_item["content"] is None
        assert test_item["score"] is None
        assert test_item["title"] == "Item with Null Fields"

    def test_get_items_ordering_consistency(self, client: TestClient, test_items: list[ContentItem]):
        """Test that items are consistently ordered by published_at desc."""
        # Make multiple requests to ensure consistent ordering
        responses = []
        for _ in range(3):
            response = client.get("/api/v1/items/")
            assert response.status_code == 200
            responses.append(response.json())
        
        # Verify all responses have the same ordering
        first_response_ids = [item["id"] for item in responses[0]["items"]]
        
        for response in responses[1:]:
            response_ids = [item["id"] for item in response["items"]]
            assert response_ids == first_response_ids, "Item ordering should be consistent across requests"