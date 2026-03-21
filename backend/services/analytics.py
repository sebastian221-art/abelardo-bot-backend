# 📄 backend/services/analytics.py
"""
Analítica del chatbot: estadísticas de conversaciones,
contactos, opt-ins, temas más consultados.
"""
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.contact      import Contact
from models.conversation import Conversation
from models.broadcast    import Broadcast


def get_general_stats(db: Session) -> dict:
    """Stats globales del dashboard."""
    now      = datetime.utcnow()
    today    = now.date()
    week_ago = now - timedelta(days=7)

    total_contacts  = db.query(Contact).count()
    opted_in        = db.query(Contact).filter(Contact.opted_in == True).count()
    opted_in_today  = db.query(Contact).filter(
        Contact.opted_in == True,
        func.date(Contact.opted_in_at) == today,
    ).count()

    msgs_today = db.query(Conversation).filter(
        func.date(Conversation.timestamp) == today,
        Conversation.role == "user",
    ).count()

    msgs_week = db.query(Conversation).filter(
        Conversation.timestamp >= week_ago,
        Conversation.role == "user",
    ).count()

    active_today = db.query(func.count(func.distinct(Conversation.phone))).filter(
        func.date(Conversation.timestamp) == today,
    ).scalar() or 0

    total_broadcasts = db.query(Broadcast).filter(Broadcast.status == "sent").count()

    optin_rate = round((opted_in / total_contacts * 100) if total_contacts else 0, 1)

    return {
        "total_contacts":   total_contacts,
        "opted_in":         opted_in,
        "opted_in_today":   opted_in_today,
        "optin_rate":       optin_rate,
        "msgs_today":       msgs_today,
        "msgs_week":        msgs_week,
        "active_today":     active_today,
        "total_broadcasts": total_broadcasts,
    }


def get_daily_messages(db: Session, days: int = 14) -> list[dict]:
    """Mensajes por día en los últimos N días."""
    start = datetime.utcnow() - timedelta(days=days)
    rows  = (
        db.query(
            func.date(Conversation.timestamp).label("date"),
            func.count(Conversation.id).label("total"),
        )
        .filter(Conversation.timestamp >= start, Conversation.role == "user")
        .group_by(func.date(Conversation.timestamp))
        .order_by(func.date(Conversation.timestamp))
        .all()
    )
    return [{"date": str(r.date), "total": r.total} for r in rows]


def get_top_intents(db: Session, days: int = 7, limit: int = 10) -> list[dict]:
    """Intenciones más frecuentes en los últimos N días."""
    start = datetime.utcnow() - timedelta(days=days)
    rows  = (
        db.query(Conversation.intent, func.count(Conversation.id).label("total"))
        .filter(
            Conversation.timestamp >= start,
            Conversation.role == "user",
            Conversation.intent != None,
            Conversation.intent != "saludo",
        )
        .group_by(Conversation.intent)
        .order_by(desc("total"))
        .limit(limit)
        .all()
    )
    return [{"intent": r.intent, "total": r.total} for r in rows]


def get_optin_curve(db: Session, days: int = 30) -> list[dict]:
    """Curva acumulada de opt-ins por día."""
    start = datetime.utcnow() - timedelta(days=days)
    rows  = (
        db.query(
            func.date(Contact.opted_in_at).label("date"),
            func.count(Contact.id).label("nuevos"),
        )
        .filter(Contact.opted_in == True, Contact.opted_in_at >= start)
        .group_by(func.date(Contact.opted_in_at))
        .order_by(func.date(Contact.opted_in_at))
        .all()
    )
    result = []
    acum   = 0
    for r in rows:
        acum += r.nuevos
        result.append({"date": str(r.date), "nuevos": r.nuevos, "acumulado": acum})
    return result