import aioodbc
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database configuration from environment variables
server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")  # Default to ODBC Driver 17

# Async function to get database connection
async def get_db_connection():
    dsn = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )

    try:
        conn = await aioodbc.connect(dsn=dsn, autocommit=True)
        print("✅ Connection successful")

        async def dict_row_factory(cursor, row):
            return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

        async with conn.cursor() as cursor:
            cursor.row_factory = dict_row_factory  # Assign row factory

        return conn  # Return the connection

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return None  # Return None in case of failure

# Test connection (Only runs if executed directly)
if __name__ == "__main__":
    import asyncio

    async def test_connection():
        conn = await get_db_connection()
        if conn:
            print("✅ Azure SQL Database Connected Successfully!")
            await conn.close()  # Ensure connection is closed
        else:
            print("❌ Failed to connect.")

    asyncio.run(test_connection())
