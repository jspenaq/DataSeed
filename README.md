# DataSeed

DataSeed is a developer-friendly data pipeline that periodically ingests content from HackerNews, Reddit, GitHub, and ProductHunt, normalizes and deduplicates it into a PostgreSQL database, exposes a read-only FastAPI REST API, and ships a Streamlit mini-dashboard with analytics.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Docker and Docker Compose
- Python 3.12+

### Installation

1.  **Clone the repository:**

    ```sh
    git clone https://github.com/your-username/DataSeed.git
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

## Running Tests

To run the tests, you can execute the following command:

```sh
docker-compose run --rm api pytest
```

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

## Running Tests

To run the tests, you can execute the following command:

```sh
docker-compose run --rm api pytest