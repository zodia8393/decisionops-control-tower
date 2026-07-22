FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libfbclient2 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir \
        firebird-driver==2.0.3 \
        "psycopg[binary]==3.2.9" \
        pydantic==2.11.7

COPY src ./src
COPY scripts/run_rdb_migration.py ./scripts/run_rdb_migration.py

ENV PYTHONPATH=/app/src

CMD ["python", "scripts/run_rdb_migration.py"]
