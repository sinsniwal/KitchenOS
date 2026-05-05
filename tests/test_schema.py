import os
import pytest
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# The connection string to the postgres container from the host
# Note: Inside docker this is different, but for local tests we use localhost if forwarded
DB_URL = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql://user:password@localhost:5432/mychef_db")

def get_conn():
    try:
        return psycopg2.connect(DB_URL)
    except Exception:
        return None

@pytest.fixture(scope="module")
def db_conn():
    conn = get_conn()
    if conn is None:
        pytest.skip("Postgres database not reachable at " + DB_URL)
    yield conn
    conn.close()

def test_family_members_table_exists(db_conn):
    """Verify that family_members table exists and has seed data."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM family_members;")
        count = cur.fetchone()[0]
        assert count >= 2  # Seed data has User and Priya

def test_dietary_profiles_table_exists(db_conn):
    """Verify that dietary_profiles table exists and has seed data."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dietary_profiles;")
        count = cur.fetchone()[0]
        assert count >= 2  # Seed data has vegetarian and peanuts

def test_pantry_has_expiry_column(db_conn):
    """Verify that pantry table has the new expiry_date column."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT expiry_date FROM pantry LIMIT 1;")
        # If it doesn't exist, this will raise an exception and fail the test
        cur.fetchone()

def test_pantry_seed_data(db_conn):
    """Verify realistic seed data in the pantry."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT item_name FROM pantry WHERE item_name = 'chicken breast';")
        assert cur.fetchone() is not None
        cur.execute("SELECT item_name FROM pantry WHERE item_name = 'heavy cream';")
        assert cur.fetchone() is not None

def test_dietary_constraint_check(db_conn):
    """Verify that invalid trait_type raises an error (CHECK constraint)."""
    with db_conn.cursor() as cur:
        try:
            cur.execute("INSERT INTO dietary_profiles (member_id, trait_type, value) VALUES (1, 'invalid', 'value');")
            db_conn.commit()
            pytest.fail("CHECK constraint on trait_type failed to catch invalid value")
        except psycopg2.errors.CheckViolation:
            db_conn.rollback()
        except Exception as e:
            db_conn.rollback()
            raise e
