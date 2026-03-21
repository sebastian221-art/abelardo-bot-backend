# 📄 backend/models/broadcast.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from models.database import Base


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(200), nullable=False)
    message         = Column(Text, nullable=False)
    media_url       = Column(String(500), nullable=True)   # imagen/audio/doc
    media_type      = Column(String(20), nullable=True)    # image/audio/document

    # Segmento objetivo
    # "all" | "city" | "department" | "interest" | "opted_in" | "segment"
    segment         = Column(String(30), default="opted_in")
    segment_value   = Column(String(100), nullable=True)   # ej: "Bogotá", "seguridad"

    # Estado
    status          = Column(String(20), default="draft")  # draft/sending/sent/failed
    total_targets   = Column(Integer, default=0)
    sent_count      = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    failed_count    = Column(Integer, default=0)

    # Fechas
    scheduled_at    = Column(DateTime, nullable=True)
    sent_at         = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    created_by      = Column(String(50), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "title":           self.title,
            "message":         self.message,
            "media_url":       self.media_url,
            "media_type":      self.media_type,
            "segment":         self.segment,
            "segment_value":   self.segment_value,
            "status":          self.status,
            "total_targets":   self.total_targets,
            "sent_count":      self.sent_count,
            "delivered_count": self.delivered_count,
            "failed_count":    self.failed_count,
            "scheduled_at":    self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at":         self.sent_at.isoformat() if self.sent_at else None,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
            "created_by":      self.created_by,
        }