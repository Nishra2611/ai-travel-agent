# Dockerfile — Week 18
# Multi-stage build: builder (Poetry install) + runtime (slim, no build tools).
# Matches pyproject.toml: Poetry, Python 3.11+, Playwright (needs system deps
# for headless Chromium — used by TravelMapGenerator's PNG thumbnail step).

# ---------- builder ----------
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=2.1.1 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
# --no-root: install deps only, package installed after source is copied
RUN poetry install --no-root --without dev --no-ansi

COPY src ./src
RUN poetry install --without dev --no-ansi

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

# System deps for Playwright's headless Chromium (thumbnail rasterization
# in travel_map_generator.py) and fpdf2's font handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
        curl fontconfig \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY src ./src
COPY data ./data

# Playwright browser binaries — only if TravelMapGenerator actually
# rasterizes maps in this environment; comment out to shrink the image
# if you move that step to a separate worker.
RUN playwright install --with-deps chromium

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "ai_travel_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]