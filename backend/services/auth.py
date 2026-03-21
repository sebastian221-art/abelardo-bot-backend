# 📄 backend/services/auth.py
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config import get_settings
from models.user import User

settings  = get_settings()
log       = logging.getLogger("abelardo_bot")
ALGORITHM = "HS256"
TOKEN_EXP = 7  # días


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub":      str(user_id),
        "username": username,
        "role":     role,
        "exp":      datetime.utcnow() + timedelta(days=TOKEN_EXP),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_user_from_token(token: str, db: Session) -> Optional[User]:
    payload = decode_token(token)
    if not payload:
        return None
    user = db.query(User).filter(
        User.id == int(payload["sub"]),
        User.is_active == True,
    ).first()
    return user


def create_default_admin(db: Session):
    """Crea el usuario admin por defecto si no existe ninguno."""
    if db.query(User).filter(User.role == "admin").first():
        return
    admin = User(
        username=       "admin",
        full_name=      "Administrador Campaña",
        hashed_password=hash_password("admin123"),
        role=           "admin",
        is_active=      True,
    )
    db.add(admin)
    db.commit()
    print("  👑  Admin creado  →  usuario: admin  |  contraseña: admin123")
    print("  ⚠️   CAMBIA LA CONTRASEÑA ANTES DE PRODUCCIÓN")