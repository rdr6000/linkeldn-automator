from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Ensure data directory exists
db_path = settings.DATABASE_URL.replace("sqlite:///", "")
if db_path.startswith("./"):
    db_path = db_path[2:]
Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and run lightweight migrations."""
    Base.metadata.create_all(bind=engine)
    # Check if progress_pct column exists in SQLite jobs table
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT progress_pct FROM jobs LIMIT 1;"))
        except Exception:
            try:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN progress_pct INTEGER DEFAULT 0;"))
                conn.commit()
            except Exception:
                pass
