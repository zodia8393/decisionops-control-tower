FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY docs ./docs

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src
ENV OUTPUT_ROOT=/data/decisionops-control-tower
ENV HOST=0.0.0.0
ENV PORT=8093
ENV LOG_LEVEL=INFO

EXPOSE 8093

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8093') + '/health', timeout=3).read()"

CMD ["sh", "-c", "uvicorn decisionops_control_tower.app:app --host ${HOST:-0.0.0.0} --port ${PORT:-8093} --no-access-log"]
