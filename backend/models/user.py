# 📄 backend/models/user.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from models.database import Base

ROLE_LABELS = {
    "admin":   "Administrador",
    "editor":  "Editor de contenido",
    "viewer":  "Solo lectura",
}


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    full_name       = Column(String(100))
    hashed_password = Column(String(200), nullable=False)
    role            = Column(String(20), default="viewer")  # admin/editor/viewer
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "username":   self.username,
            "full_name":  self.full_name,
            "role":       self.role,
            "role_label": ROLE_LABELS.get(self.role, self.role),
            "is_active":  self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }