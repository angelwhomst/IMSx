#!/bin/bash
echo "🔍 Checking for existing ODBC drivers..."
odbcinst -q -d

echo "🔍 Checking if ODBC Driver 17 is already installed..."
if odbcinst -q -d | grep -q "ODBC Driver 17 for SQL Server"; then
    echo "✅ ODBC Driver 17 is already installed!"
else
    echo "📥 Downloading and extracting ODBC Driver 17..."
    
    # Create local directory for ODBC drivers
    mkdir -p $HOME/odbc

    # Download ODBC Driver 17 (Ubuntu version)
    curl -L -o $HOME/odbc/msodbcsql17.tar.gz "https://packages.microsoft.com/ubuntu/18.04/prod/pool/main/m/msodbcsql17/msodbcsql17_17.10.2.1-1_amd64.deb"

    # Extract ODBC Driver files
    tar -xvf $HOME/odbc/msodbcsql17.tar.gz -C $HOME/odbc/

    # Set environment variables
    export ODBCINI=$HOME/odbc/odbc.ini
    export ODBCSYSINI=$HOME/odbc/
    export PATH=$HOME/odbc:$PATH

    echo "✅ ODBC Driver 17 installed successfully."
fi

echo "🔄 Installing Python dependencies..."
pip install -r requirements.txt

echo "🚀 Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 8000