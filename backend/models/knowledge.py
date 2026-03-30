# 📄 backend/models/knowledge.py  ← REEMPLAZA EL ANTERIOR
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from models.database import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String(200), nullable=False)
    category   = Column(String(80),  nullable=False)
    content    = Column(Text,        nullable=False)
    source     = Column(String(50),  default="manual")  # manual | web_scrape | import
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "title":      self.title,
            "category":   self.category,
            "content":    self.content,
            "source":     self.source or "manual",
            "active":     self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }