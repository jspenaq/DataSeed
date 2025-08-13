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

### API Usage

Here are a few examples of how to query the API using `curl`:

**1. Get the latest items from all sources:**

```sh
curl http://localhost:8000/api/v1/items/
```

**2. Get the latest items from a specific source (e.g., HackerNews):**

```sh
curl http://localhost:8000/api/v1/items/?source_name=hackernews
```

**3. Search for items with a query (e.g., "AI"):**

```sh
curl http://localhost:8000/api/v1/items/?q=AI
```

**4. Paginate results (get 5 items, skipping the first 10):**

```sh
curl http://localhost:8000/api/v1/items/?limit=5&offset=10
```

**5. Combine filters (search for "Python" in "github" source):**

```sh
curl http://localhost:8000/api/v1/items/?source_name=github&q=Python
```

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