# DataSeed

DataSeed is a developer-friendly data pipeline that periodically ingests content from HackerNews, Reddit, GitHub, and ProductHunt, normalizes and deduplicates it into a PostgreSQL database, exposes a read-only FastAPI REST API, and ships a Streamlit mini-dashboard with analytics.

## Features

- **Multi-Source ETL Pipeline**: Automated extraction from public APIs (HackerNews, Reddit, GitHub, ProductHunt)
- **Data Normalization**: Pydantic-based validation, deduplication, and cleaning
- **REST API**: Clean, well-documented endpoints with filtering and pagination
- **Dashboard**: Streamlit-based interface for data exploration
- **Containerized**: Docker-based development and deployment
- **Scheduled Updates**: Automated data refresh every 15 minutes

## Project Structure

```
DataSeed/
├── app/                      # Main application code
│   ├── api/                  # API endpoints
│   ├── core/                 # Business logic
│   ├── models/               # Database models
│   ├── schemas/              # Pydantic schemas
│   └── workers/              # Celery tasks
├── dashboard/                # Streamlit dashboard
├── migrations/               # Alembic migrations
├── config/                   # Configuration files
├── docker/                   # Docker configuration
├── tests/                    # Test suite
└── scripts/                  # Utility scripts
```

## Prerequisites

- Docker and Docker Compose
- Python 3.12+
- Git

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/DataSeed.git
cd DataSeed
```

### 2. Create environment file

Create a `.env` file in the project root with the following content (adjust as needed):

```
# Database
DATABASE_URL=postgresql+asyncpg://dataseed:dataseed@db:5432/dataseed

# Task Queue
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# External APIs
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
GITHUB_TOKEN=ghp_your_token
PRODUCTHUNT_TOKEN=your_token

# Application
LOG_LEVEL=INFO
API_V1_STR=/api/v1
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8501"]
```

### 3. Start the development environment

```bash
docker-compose up -d
```

This will start the following services:
- PostgreSQL database
- Redis for Celery
- FastAPI application
- Celery worker
- Streamlit dashboard

### 4. Initialize the database

```bash
docker-compose exec api python scripts/init_db.py
```

### 5. Access the services

- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Dashboard: http://localhost:8501

## Development Workflow

### Running tests

```bash
# Run all tests
docker-compose exec api pytest

# Run with coverage
docker-compose exec api coverage run -m pytest
docker-compose exec api coverage report
```

### Database migrations

```bash
# Create a new migration
docker-compose exec api alembic revision --autogenerate -m "Description of changes"

# Apply migrations
docker-compose exec api alembic upgrade head
```

### Linting and formatting

```bash
# Run linting
docker-compose exec api ruff check .

# Format code
docker-compose exec api ruff format .
```

## API Endpoints

### Health Check

```
GET /api/v1/health
```

Returns the health status of the system.

### Sources

```
GET /api/v1/sources
```

Returns a list of all data sources.

### Items

```
GET /api/v1/items
```

Returns a list of content items with filtering options:

- `source`: Filter by source name (e.g., `hackernews`, `reddit`)
- `q`: Search query
- `limit`: Maximum number of items to return (default: 20)
- `offset`: Pagination offset

## Architecture

DataSeed follows a modular architecture with the following components:

1. **Extractors**: Source-specific modules that fetch data from external APIs
2. **Normalizers**: Transform raw data into a common schema
3. **Database**: PostgreSQL with SQLAlchemy ORM
4. **API**: FastAPI with automatic documentation
5. **Task Queue**: Celery for scheduled and background tasks
6. **Dashboard**: Streamlit for data visualization

For more details, see the [architecture documentation](docs/architecture.md).

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.