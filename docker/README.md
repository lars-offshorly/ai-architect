# Docker Infrastructure for AI Architect

This directory contains all Docker-related files for building and deploying the AI Architect application.

## Quick Start

### Build the image:
```bash
cd /path/to/ai-architect
docker build -f docker/Dockerfile -t ai-architect:latest .
```

### Run with Docker Compose:
```bash
cd docker
docker-compose up -d
```

### Run standalone container:
```bash
docker run -d \
  --name ai-architect \
  -p 8000:8000 \
  --env-file .env \
  ai-architect:latest /code/docker/start_app.sh
```

## Files

- **`Dockerfile`** - Container image definition
- **`.dockerignore`** - Files excluded from Docker build
- **`entrypoint.sh`** - Container entrypoint script
- **`start_app.sh`** - Application startup script
- **`docker-compose.yml`** - Local development orchestration
- **`DEPLOYMENT.md`** - Full deployment guide for DevOps

## Documentation

For complete deployment instructions, environment variables, and troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Requirements

- Docker 20.10+
- Docker Compose 2.0+ (for docker-compose.yml)
- `.env` file in project root with required configuration
