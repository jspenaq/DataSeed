FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml .

# Install deps into a local venv at /app/.venv
RUN uv sync

# Make that venv the default for all processes
# ENV VIRTUAL_ENV=/app/.venv
# ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]