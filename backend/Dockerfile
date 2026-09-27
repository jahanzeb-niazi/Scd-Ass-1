# syntax=docker/dockerfile:1
# TODO(you): pin this to a digest for the bonus (§3.1 "Pin by digest for the bonus")
FROM python:3.12-slim AS builder

WORKDIR /build

# Cache-friendly layer order: dependency manifest before source (§3.1)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

# TODO(you): confirm this matches your distro's non-root convention
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

COPY --from=builder /install /usr/local
WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# TODO(you): confirm /health does NOT touch the DB before wiring this healthcheck (§2.2)
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status==200 else 1)"

# Exec form, per §3.1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
