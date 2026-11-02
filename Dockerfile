FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]"
COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY docs ./docs
COPY data/validation ./data/validation
COPY data/capabilities ./data/capabilities
ENV PYTHONPATH=/app/src
EXPOSE 8000
