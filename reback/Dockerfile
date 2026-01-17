# Dockerfile for ICFES Analytics Platform
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy package.json and gulpfile first (for better caching)
COPY reback/package.json reback/gulpfile.js ./

# Install npm dependencies
RUN npm install

# Copy requirements folder
COPY reback/requirements/ requirements/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements/production.txt

# Copy all project files (maintain reback folder structure for Gulp)
COPY reback/ ./reback/

# Build frontend assets with Gulp
RUN npm run build

# Move built files to app root for Django
RUN cp -r reback/* . && rm -rf reback

# Create directory for DuckDB
RUN mkdir -p /app/data

# Expose port (Railway will set PORT env var)
EXPOSE 8000

# Run gunicorn
CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
