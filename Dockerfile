# Use Python 3.11 base image
FROM python:3.11

# Update package list
RUN apt-get update

# Install dependencies for MSSQL ODBC
RUN apt-get install -y tdsodbc unixodbc-dev unixodbc
RUN apt-get install -y curl apt-transport-https

# Add Microsoft repository and install ODBC driver
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update
RUN ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Upgrade pip
RUN pip install --upgrade pip

# Copy project files
WORKDIR /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the FastAPI port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
