#Apertura della connessione al database SQLite (data/travel.db) e la fornisce
#agli endpoint che ne hanno bisogno, chiudendola automaticamente dopo

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
DB_PATH = ROOT_DIR / "data" / "travel.db"

engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)


def get_db():
    # "Dependency" di FastAPI: apre una sessione, la passa all'endpoint, poi la chiude
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()