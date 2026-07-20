import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:your_password@localhost:5432/querypal"
)

# Direct (non-pooled) connection, used for DDL such as CREATE TABLE — more
# reliable for schema changes than a pgbouncer transaction-mode pooled URL.
# Falls back to DATABASE_URL when unset (e.g. plain local Postgres, no pooler).
DATABASE_URL_DIRECT = os.getenv("DATABASE_URL_DIRECT", DATABASE_URL)

# PostgreSQL does not need check_same_thread
engine = create_engine(DATABASE_URL)
direct_engine = create_engine(DATABASE_URL_DIRECT)

def get_engine():
    return engine

def get_direct_engine():
    return direct_engine

def test_connection():
    """Quick check that the DB is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL connected successfully.")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False