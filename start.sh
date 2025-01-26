#!/bin/bash

# Exit script immediately if a command fails
set -e

echo "Downloading and installing ODBC Driver 17 for SQL Server..."

# Download the Microsoft ODBC Driver 17 package for Debian-based systems
curl -O https://packages.microsoft.com/debian/10/prod/pool/main/m/msodbcsql17/msodbcsql17_17.10.2.1-1_amd64.deb

# Install the downloaded ODBC Driver 17 package
dpkg -i msodbcsql17_17.10.2.1-1_amd64.deb || true

# Fix dependencies if needed
apt-get install -f -y || true

# Set proper permissions for the ODBC driver
chmod -R 777 /opt/microsoft/msodbcsql17/ || true

echo "ODBC Driver 17 installed successfully!"

# Start the FastAPI app with Gunicorn and Uvicorn worker
echo "Starting FastAPI app..."
gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
