FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# libpq for PostgreSQL. PDFs are drawn with fpdf2 (pure Python), so no system libraries are needed for them.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Install dependencies first so this layer is cached until pyproject.toml/uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
# Strip CRLF in case the repo was checked out on Windows (git autocrlf), otherwise bash fails to start it
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh \
    && useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000

# Migrate, collectstatic, then serve ASGI with uvicorn
CMD ["/app/entrypoint.sh"]
