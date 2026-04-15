# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /code

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /code/

# Install dependencies
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    pip3 install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root

# Make entrypoint scripts executable
RUN chmod +x docker/entrypoint.sh && \
    chmod +x docker/start_app.sh

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/code/docker/entrypoint.sh"]
