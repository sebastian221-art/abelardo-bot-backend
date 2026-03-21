# 📄 backend/models/contact.py
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from models.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id            = Column(Integer, primary_key=True, index=True)
    phone         = Column(String(20), unique=True, index=True, nullable=False)
    name          = Column(String(100))
    city          = Column(String(100), index=True)
    department    = Column(String(100))

    # Opt-in
    opted_in      = Column(Boolean, default=False)
    opted_in_at   = Column(DateTime, nullable=True)
    opted_out_at  = Column(DateTime, nullable=True)

    # Segmentación
    interests     = Column(Text, default="[]")   # JSON: ["seguridad", "empleo"]
    segment       = Column(String(50), default="general")  # general/activo/embajador
    source        = Column(String(50), default="firma")    # firma/broadcast/referido
    referred_by   = Column(String(20), nullable=True)      # phone de quien lo invitó

    # Actividad
    total_msgs    = Column(Integer, default=0)
    last_seen     = Column(DateTime, nullable=True)
    referrals     = Column(Integer, default=0)   # cuántos invitó
    created_at    = Column(DateTime, default=datetime.utcnow)

    # ── helpers ──────────────────────────────────────────────────
    def get_interests(self) -> list[str]:
        try:
            return json.loads(self.interests or "[]")
        except Exception:
            return []

    def add_interest(self, interest: str):
        lst = self.get_interests()
        if interest not in lst:
            lst.append(interest)
            self.interests = json.dumps(lst)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "phone":       self.phone,
            "name":        self.name,
            "city":        self.city,
            "department":  self.department,
            "opted_in":    self.opted_in,
            "opted_in_at": self.opted_in_at.isoformat() if self.opted_in_at else None,
            "opted_out_at":self.opted_out_at.isoformat() if self.opted_out_at else None,
            "interests":   self.get_interests(),
            "segment":     self.segment,
            "source":      self.source,
            "referred_by": self.referred_by,
            "total_msgs":  self.total_msgs,
            "referrals":   self.referrals,
            "last_seen":   self.last_seen.isoformat() if self.last_seen else None,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }