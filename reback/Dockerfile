# Dockerfile for ICFES Analytics Platform
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies including Node.js and AWS CLI
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements folder
COPY reback/requirements/ requirements/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements/production.txt

# Copy all project files from reback folder
COPY reback/ .

# Note: Using pre-compiled CSS/JS files from repository
# Gulp build step skipped to avoid build complexity
# Assets are already compiled and committed to repo

# Collect static files at build time so WhiteNoise has them on startup.
# DATABASE_URL and SECRET_KEY are required by settings at import time even
# though collectstatic doesn't actually connect to any database.
ARG DJANGO_SECRET_KEY=build-only-not-real
ARG DATABASE_URL=sqlite:////tmp/build.db
RUN DATABASE_URL=${DATABASE_URL} DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY} \
    python manage.py collectstatic --noinput --settings=config.settings.railway

# Create directory for DuckDB
RUN mkdir -p /app/data

# Expose port (Railway will set PORT env var)
EXPOSE 8000

# Run gunicorn (optimized: 1 worker, 8 threads for lower memory usage)
CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120
