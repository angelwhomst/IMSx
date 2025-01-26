#!/bin/bash

# Exit script on any error
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting FastAPI app..."
uvicorn main:app --host 0.0.0.0 --port 8000
