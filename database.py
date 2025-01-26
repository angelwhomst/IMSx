import aioodbc
import os
from dotenv import load_dotenv

# load environment variables from .env file
load_dotenv()

# get database configuration from environment variables
server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
driver = os.getenv("DB_DRIVER")

# async function to get database connection
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
        print("Connection successful")

        async def dict_row_factory(cursor, row):
            return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

        conn.row_factory = dict_row_factory  # Assign row factory before returning

        return conn  # return the connection

    except Exception as e:
        print("Connection failed:", str(e))
        return None  # return None in case of failure


import asyncio

async def test_connection():
    conn = await get_db_connection()
    if conn:
        print("Azure SQL Database Connected Successfully!")
    else:
        print("Failed to connect.")

asyncio.run(test_connection())

