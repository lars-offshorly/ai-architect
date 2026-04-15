#!/bin/bash

echo "Starting FastAPI application with Uvicorn"
cd /code
PYTHONPATH=src poetry run uvicorn main:app --host 0.0.0.0 --port 8000
