import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:your_password@localhost:5432/querypal"
)

# PostgreSQL does not need check_same_thread
engine = create_engine(DATABASE_URL)

def get_engine():
    return engine

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