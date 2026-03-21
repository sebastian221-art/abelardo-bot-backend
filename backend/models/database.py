# 📄 backend/models/database.py  ← REEMPLAZA EL ANTERIOR
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    # Importar todos los modelos para que SQLAlchemy los registre
    from models import contact, conversation, broadcast, broadcast_log, user, knowledge  # noqa
    Base.metadata.create_all(bind=engine)