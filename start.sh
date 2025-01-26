#!/bin/bash
# Install dependencies
apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev

# Add Microsoft package repository
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
echo "deb https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/mssql-release.list

# Install ODBC Driver 17 for SQL Server
apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Start the FastAPI app with Gunicorn
gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
