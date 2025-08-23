# DataSeed

DataSeed is a developer-friendly data pipeline that periodically ingests content from HackerNews, Reddit, GitHub, and ProductHunt, normalizes and deduplicates it into a PostgreSQL database, exposes a read-only FastAPI REST API, and ships a Streamlit mini-dashboard with analytics.

## Features

- **Multi-Source ETL Pipeline**: Automated extraction from public APIs (HackerNews, Reddit, GitHub, ProductHunt).
- **Data Normalization**: Pydantic-based validation, deduplication, and cleaning for consistent data quality.
- **Public API**: RESTful read-only API with filtering, search, and sorting capabilities.
- **Mini Dashboard**: Streamlit-based interface for data exploration and visualization.
- **Scheduled Updates**: Automated data refresh with retry/backoff mechanisms for reliability.
- **Monitoring**: Simple counters and health checks for pipeline status.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Docker and Docker Compose
- Python 3.12+

### Installation

1.  **Clone the repository:**

    ```sh
    git clone https://github.com/jspenaq/DataSeed.git
    cd DataSeed
    ```

2.  **Set up the environment variables:**

    Create a `.env` file by copying the example file.

    ```sh
    cp .env.example .env
    ```

    Update the `.env` file with your actual credentials for the external APIs (Reddit, GitHub, ProductHunt).

3.  **Build and run the services using Docker Compose:**

    ```sh
    docker-compose up --build
    ```

    This will start the following services:
    -   `db`: PostgreSQL database
    -   `redis`: Redis server for Celery
    -   `api`: FastAPI application
    -   `worker`: Celery worker for data ingestion
    -   `dashboard`: Streamlit dashboard

## Usage

-   **API**: The API will be available at `http://localhost:8000`. You can access the auto-generated documentation at `http://localhost:8000/docs`.
-   **Dashboard**: The Streamlit dashboard will be available at `http://localhost:8501`.

### Dashboard

The DataSeed Dashboard is a comprehensive Streamlit-based web interface that provides real-time insights and analytics for your data pipeline. It offers an intuitive way to explore content from all connected sources, monitor system health, and analyze trends.

#### Features

- **📊 Overview Page**: Real-time KPIs, system health monitoring, trending items, and latest content with search and filtering
- **🔗 Sources Page**: Data source management, ingestion statistics, health monitoring, and detailed run history
- **📈 Analytics Page**: Interactive charts, trend analysis, data export capabilities, and comprehensive filtering options
- **🔄 Auto-Refresh**: Configurable automatic data updates with rate limiting awareness
- **📱 Mobile Responsive**: Optimized interface that works seamlessly on desktop, tablet, and mobile devices
- **📤 Data Export**: CSV, JSON, and Excel export functionality for all data tables
- **🎯 Advanced Filtering**: Search, source filtering, time windows, and custom queries

#### Running the Dashboard

To run the dashboard locally:

```sh
# Using Docker Compose (recommended)
docker-compose up dashboard

# Or run directly with Streamlit
streamlit run dashboard/main.py
```

The dashboard will be available at `http://localhost:8501`.

#### Environment Variables

The dashboard requires the following environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_BASE_URL` | Base URL for the DataSeed API | `http://localhost:8000` | No |
| `DASHBOARD_TITLE` | Custom title for the dashboard | `DataSeed Dashboard` | No |
| `TELEMETRY_ENABLED` | Enable telemetry logging | `true` | No |
| `TELEMETRY_LOG_FILE` | Path to telemetry log file | `dashboard_telemetry.log` | No |

Example `.env` configuration:
```env
API_BASE_URL=http://localhost:8000
DASHBOARD_TITLE=My DataSeed Dashboard
TELEMETRY_ENABLED=true
TELEMETRY_LOG_FILE=logs/dashboard_telemetry.log
```

#### Dashboard Pages

**Overview Page**
- System health indicators (API, Database, Redis)
- Key performance indicators (total items, success rate, ingestion lag)
- Trending items from the last 24 hours
- Latest content with real-time search and filtering
- Export functionality for search results

**Sources Page**
- Overview of all configured data sources
- Health status monitoring for each source
- Detailed ingestion statistics and run history
- Performance metrics and error tracking
- Source-specific filtering and analysis

**Analytics Page**
- Interactive time-series charts showing ingestion trends
- Source comparison and distribution analysis
- Score distribution histograms
- Trending content analysis
- Advanced filtering by time window, sources, and search queries
- Comprehensive data export capabilities

#### Auto-Refresh Feature

The dashboard includes intelligent auto-refresh functionality:

- **Configurable Intervals**: 15 seconds to 10 minutes
- **Rate Limiting Awareness**: Automatically pauses when API rate limits are hit
- **Manual Controls**: Pause, resume, and manual refresh options
- **Visual Indicators**: Progress bars and countdown timers
- **Mobile Optimized**: Touch-friendly controls on mobile devices

#### Telemetry and Monitoring

The dashboard includes built-in telemetry for monitoring user interactions and system performance:

- **Page Views**: Track navigation patterns
- **User Actions**: Monitor feature usage and interactions
- **API Performance**: Track request durations and success rates
- **Rate Limiting**: Monitor and alert on API rate limit events
- **Export Activity**: Track data export usage patterns

Telemetry data is logged to console and optionally to file for analysis.

#### Mobile Responsiveness

The dashboard is fully responsive and optimized for mobile devices:

- **Adaptive Layouts**: Automatically adjusts to screen size
- **Touch-Friendly Controls**: Optimized buttons and interactions
- **Collapsible Sidebar**: Space-efficient navigation on mobile
- **Readable Typography**: Optimized text sizes and spacing
- **Fast Loading**: Optimized for mobile network conditions

For detailed usage instructions and screenshots, see the [Dashboard Guide](docs/dashboard_guide.md).

### API Usage

The DataSeed API provides several endpoints for accessing content items, statistics, and trending data. Here are comprehensive examples using `curl`:

#### Content Items Endpoints

**1. Get the latest items from all sources (offset pagination):**

```sh
curl http://localhost:8000/api/v1/items/
```

**2. Get the latest items from a specific source:**

```sh
curl http://localhost:8000/api/v1/items/?source_name=hackernews
```

**3. Search for items with a query:**

```sh
curl http://localhost:8000/api/v1/items/?q=artificial%20intelligence
```

**4. Paginate results (get 5 items, skipping the first 10):**

```sh
curl http://localhost:8000/api/v1/items/?limit=5&offset=10
```

**5. Combine filters (search for "Python" in "github" source):**

```sh
curl http://localhost:8000/api/v1/items/?source_name=github&q=Python
```

**6. Get items using cursor-based pagination (recommended for large datasets):**

```sh
curl http://localhost:8000/api/v1/items/cursor
```

**7. Get next page using cursor from previous response:**

```sh
curl "http://localhost:8000/api/v1/items/cursor?cursor=MjAyNC0wMS0xNVQxMDozMDowMFo6MTIzNDU%3D"
```

**8. Search with cursor pagination:**

```sh
curl "http://localhost:8000/api/v1/items/cursor?q=machine%20learning&limit=10"
```

#### Statistics Endpoints

**9. Get overall statistics for the last 24 hours:**

```sh
curl http://localhost:8000/api/v1/items/stats
```

**10. Get statistics for a specific time window (7 days):**

```sh
curl http://localhost:8000/api/v1/items/stats?window=7d
```

**11. Get statistics for a specific source:**

```sh
curl http://localhost:8000/api/v1/items/stats?source_name=hackernews&window=24h
```

#### Trending Items Endpoints

**12. Get trending items from the last 24 hours:**

```sh
curl http://localhost:8000/api/v1/items/trending
```

**13. Get trending items from the last week:**

```sh
curl http://localhost:8000/api/v1/items/trending?window=7d
```

**14. Get trending items using hot score algorithm:**

```sh
curl http://localhost:8000/api/v1/items/trending?use_hot_score=true&window=24h
```

**15. Get trending items from a specific source:**

```sh
curl http://localhost:8000/api/v1/items/trending?source_name=reddit&window=24h&limit=10
```

#### Health and Sources Endpoints

**16. Check API health:**

```sh
curl http://localhost:8000/api/v1/health
```

**17. Get available data sources:**

```sh
curl http://localhost:8000/api/v1/sources
```

**18. Get overall system statistics:**

```sh
curl http://localhost:8000/api/v1/stats
```

#### Advanced Examples

**19. Complex filtering with multiple parameters:**

```sh
curl "http://localhost:8000/api/v1/items/?source_name=hackernews&q=AI&limit=20&offset=0"
```

**20. Get trending items with hot score for multiple sources:**

```sh
curl "http://localhost:8000/api/v1/items/trending?window=24h&use_hot_score=true&limit=50"
```

All endpoints support JSON responses and include appropriate HTTP caching headers for optimal performance.

## Running Tests

To run the tests, you can execute the following command:

```sh
docker-compose run --rm api pytest
```

## Project Structure

```
DataSeed/
├── app/                     # Core application logic (FastAPI, models, services, workers)
├── dashboard/               # Streamlit dashboard application
├── migrations/              # Alembic database migrations
├── config/                  # Configuration files (e.g., source definitions)
├── tests/                   # Unit, integration, and API tests
├── docker/                  # Docker-related files (Dockerfile, docker-compose.yml)
└── scripts/                 # Utility scripts
```

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Ensure your code adheres to the project's coding style and passes all tests.
5.  Commit your changes (`git commit -m 'feat: Add new feature'`).
6.  Push to the branch (`git push origin feature/your-feature-name`).
7.  Open a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.