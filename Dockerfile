FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
RUN uv sync --frozen --no-dev

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source code
COPY . .

# Expose Django port
EXPOSE 8000

# Run development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

