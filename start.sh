#!/bin/bash

echo "🔄 Updating package lists..."
sudo apt-get update -y

echo "📥 Installing required dependencies..."
sudo apt-get install -y curl gnupg2 unixodbc unixodbc-dev

echo "🔑 Adding Microsoft package signing key..."
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -

echo "📌 Adding Microsoft SQL Server ODBC Driver repository..."
sudo add-apt-repository "$(wget -qO- https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list)"

echo "📥 Installing ODBC Driver 17 for SQL Server..."
sudo apt-get update -y
ACCEPT_EULA=Y sudo apt-get install -y msodbcsql17

echo "✅ ODBC Driver 17 installation complete."

echo "🔄 Installing Python dependencies..."
pip install -r requirements.txt

echo "🚀 Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 8000
