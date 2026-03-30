# 📄 backend/models/contact_group.py  ← ARCHIVO NUEVO
"""
Modelo para grupos/segmentos personalizados de contactos.
Permite crear grupos como 'Defensoras', 'Líderes', 'Jóvenes', etc.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base

# Tabla de relación many-to-many entre contactos y grupos
contact_group_members = Table(
    "contact_group_members",
    Base.metadata,
    Column("group_id",   Integer, ForeignKey("contact_groups.id"), primary_key=True),
    Column("contact_id", Integer, ForeignKey("contacts.id"),       primary_key=True),
)


class ContactGroup(Base):
    __tablename__ = "contact_groups"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), unique=True, nullable=False)  # ej: "Defensoras"
    description = Column(String(300), default="")
    color       = Column(String(7),   default="#6366f1")  # color hex para el panel
    icon        = Column(String(10),  default="👥")
    created_at  = Column(DateTime, default=datetime.utcnow)

    members = relationship("Contact", secondary=contact_group_members, backref="groups")

    def to_dict(self, include_count: bool = True) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "color":       self.color,
            "icon":        self.icon,
            "count":       len(self.members) if include_count else 0,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }