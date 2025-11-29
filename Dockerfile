# ================================
# Stage 0 — Fetch uv binary (pinned)
# ================================
# Using a pinned uv version gives reproducible builds.
FROM ghcr.io/astral-sh/uv:0.9.11 AS uv-source


# ================================
# Stage 1 — Application Build Image
# ================================
FROM python:3.14-slim-bookworm AS builder

# Install system dependencies required for:
# - GeoDjango (GDAL, GEOS)
# - psycopg2
# - Building Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    gdal-bin \
    libgdal-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binaries from Stage 0
COPY --from=uv-source /uv /uvx /bin/

WORKDIR /app

# === Copy only dependency manifests first to improve cache performance ===
COPY pyproject.toml uv.lock* /app/

# === Install dependencies into a Python virtual environment ===
# BuildKit cache makes repeated builds much faster.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --compile-bytecode --no-editable

# === Copy full project source ===
COPY . /app/

# === Install project itself (non-editable for clean production builds) ===
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


# ================================
# Stage 2 — Final Runtime Image
# ================================
FROM python:3.14-slim-bookworm

# Copy all system libs needed for runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from builder stage
COPY --from=uv-source /uv /uvx /bin/

WORKDIR /app

# Copy only installed virtual environment (+ bytecode)
COPY --from=builder /app/.venv /app/.venv

# Copy entrypoint and project source code
COPY --from=builder /app /app

# Activate venv automatically
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# GDAL path if needed by GeoDjango
ENV GDAL_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgdal.so

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
