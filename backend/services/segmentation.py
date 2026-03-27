# 📄 backend/services/segmentation.py  ← REEMPLAZA EL ANTERIOR
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.contact import Contact


def get_contacts_for_broadcast(
    db:            Session,
    segment:       str = "todos",
    segment_value: str = "",
) -> list[Contact]:
    """
    Segmentos disponibles:
    - "todos"       → todos los contactos importados
    - "all"         → alias de todos
    - "opted_in"    → solo los que aceptaron recibir mensajes
    - "city"        → filtrados por ciudad
    - "department"  → filtrados por departamento
    - "interest"    → filtrados por interés
    - "segment"     → filtrados por segmento (general/activo/embajador)
    """
    # Base: todos los contactos
    q = db.query(Contact)

    if segment in ("todos", "all"):
        pass  # sin filtro — todos

    elif segment == "opted_in":
        q = q.filter(Contact.opted_in == True)

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
    segment:       str = "todos",
    segment_value: str = "",
) -> int:
    return len(get_contacts_for_broadcast(db, segment, segment_value))


def get_city_stats(db: Session) -> list[dict]:
    rows = (
        db.query(Contact.city, func.count(Contact.id).label("total"))
        .filter(Contact.city != None)
        .group_by(Contact.city)
        .order_by(func.count(Contact.id).desc())
        .all()
    )
    return [{"city": r.city, "total": r.total} for r in rows]


def get_ambassador_ranking(db: Session, limit: int = 20) -> list[dict]:
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