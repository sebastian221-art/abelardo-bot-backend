# 📄 backend/models/broadcast.py  ← REEMPLAZA EL ANTERIOR
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from models.database import Base


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id             = Column(Integer, primary_key=True, index=True)
    title          = Column(String(200), nullable=False)
    message        = Column(Text, default="")
    template_name  = Column(String(100), nullable=True)   # ← plantilla aprobada
    segment        = Column(String(50),  default="todos")
    segment_value  = Column(String(100), nullable=True)
    media_url      = Column(Text,        nullable=True)
    media_type     = Column(String(20),  nullable=True)
    status         = Column(String(20),  default="draft")
    total_targets  = Column(Integer,     default=0)
    sent_count     = Column(Integer,     default=0)
    failed_count   = Column(Integer,     default=0)
    scheduled_at   = Column(DateTime,    nullable=True)
    sent_at        = Column(DateTime,    nullable=True)
    created_by     = Column(String(100), default="admin")
    created_at     = Column(DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":            self.id,
            "title":         self.title,
            "message":       self.message or "",
            "template_name": self.template_name or "",
            "segment":       self.segment,
            "segment_value": self.segment_value or "",
            "media_url":     self.media_url or "",
            "media_type":    self.media_type or "",
            "status":        self.status,
            "total_targets": self.total_targets,
            "sent_count":    self.sent_count,
            "failed_count":  self.failed_count,
            "scheduled_at":  self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at":       self.sent_at.isoformat() if self.sent_at else None,
            "created_by":    self.created_by,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }