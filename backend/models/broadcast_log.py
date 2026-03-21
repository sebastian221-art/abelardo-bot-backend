# 📄 backend/models/broadcast_log.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from models.database import Base


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id           = Column(Integer, primary_key=True, index=True)
    broadcast_id = Column(Integer, ForeignKey("broadcasts.id"), index=True)
    phone        = Column(String(20), index=True, nullable=False)
    status       = Column(String(20), default="pending")  # pending/sent/delivered/failed
    error        = Column(String(300), nullable=True)
    sent_at      = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "broadcast_id": self.broadcast_id,
            "phone":        self.phone,
            "status":       self.status,
            "error":        self.error,
            "sent_at":      self.sent_at.isoformat() if self.sent_at else None,
        }