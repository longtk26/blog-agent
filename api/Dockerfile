FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends graphviz && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src
COPY docker-entrypoint.sh .

RUN useradd --create-home --uid 1000 agent && mkdir -p /app/data && chown -R agent:agent /app
USER agent

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
