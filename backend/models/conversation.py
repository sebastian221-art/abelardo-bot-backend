# 📄 backend/models/conversation.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from models.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id        = Column(Integer, primary_key=True, index=True)
    phone     = Column(String(20), index=True, nullable=False)
    role      = Column(String(10), nullable=False)   # "user" | "assistant"
    message   = Column(Text, nullable=False)
    intent    = Column(String(50), nullable=True)    # propuesta/seguridad/empleo/salud/otro
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "phone":     self.phone,
            "role":      self.role,
            "message":   self.message,
            "intent":    self.intent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }