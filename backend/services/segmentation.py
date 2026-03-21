# 📄 backend/services/segmentation.py
"""
Segmentación de contactos para broadcasts.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.contact import Contact


def get_contacts_for_broadcast(
    db:            Session,
    segment:       str   = "opted_in",
    segment_value: str   = "",
) -> list[Contact]:
    """
    Retorna la lista de contactos según el segmento elegido.

    Segmentos disponibles:
    - "all"         → todos los contactos importados (firmantes)
    - "opted_in"    → solo los que aceptaron recibir mensajes
    - "city"        → filtrados por ciudad  (segment_value = nombre ciudad)
    - "department"  → filtrados por depto   (segment_value = nombre dpto)
    - "interest"    → filtrados por interés (segment_value = tema)
    - "segment"     → filtrados por segmento (general/activo/embajador)
    """
    q = db.query(Contact).filter(Contact.opted_in == True)

    if segment == "all":
        q = db.query(Contact)  # sin filtro de opt-in

    elif segment == "city" and segment_value:
        q = q.filter(func.lower(Contact.city) == segment_value.lower())

    elif segment == "department" and segment_value:
        q = q.filter(func.lower(Contact.department) == segment_value.lower())

    elif segment == "interest" and segment_value:
        q = q.filter(Contact.interests.contains(segment_value.lower()))

    elif segment == "segment" and segment_value:
        q = q.filter(Contact.segment == segment_value.lower())

    return q.all()


def count_contacts_for_broadcast(
    db:            Session,
    segment:       str = "opted_in",
    segment_value: str = "",
) -> int:
    return len(get_contacts_for_broadcast(db, segment, segment_value))


def get_city_stats(db: Session) -> list[dict]:
    """Retorna cantidad de contactos opt-in por ciudad."""
    rows = (
        db.query(Contact.city, func.count(Contact.id).label("total"))
        .filter(Contact.opted_in == True, Contact.city != None)
        .group_by(Contact.city)
        .order_by(func.count(Contact.id).desc())
        .all()
    )
    return [{"city": r.city, "total": r.total} for r in rows]


def get_ambassador_ranking(db: Session, limit: int = 20) -> list[dict]:
    """Ranking de embajadores por cantidad de referidos."""
    rows = (
        db.query(Contact)
        .filter(Contact.referrals > 0)
        .order_by(Contact.referrals.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "phone":     r.phone,
            "name":      r.name or "Sin nombre",
            "city":      r.city,
            "referrals": r.referrals,
        }
        for r in rows
    ]