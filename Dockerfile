FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY ui ./ui

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[app,demo]"

EXPOSE 8000 8501

CMD ["creativebench-api"]
