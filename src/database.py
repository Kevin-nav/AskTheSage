from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from src.config import DATABASE_URL

if not DATABASE_URL:
    # This check is also in config.py, but kept here as a safeguard.
    raise ValueError("No DATABASE_URL set for the database connection")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    """Context manager to yield a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()