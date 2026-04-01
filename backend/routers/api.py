# 📄 backend/routers/api.py  ← REEMPLAZA EL ANTERIOR
"""
Endpoints generales del panel: contactos, conversaciones, stats, chat-test.
"""
import csv
import io
import re
from datetime    import datetime
from fastapi     import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic    import BaseModel
from typing      import Optional
from sqlalchemy.orm import Session
from sqlalchemy  import desc, func

from models.database     import get_db
from models.contact      import Contact
from models.conversation import Conversation
from services.analytics  import (
    get_general_stats, get_daily_messages,
    get_top_intents, get_optin_curve,
)
from services.segmentation import get_city_stats, get_ambassador_ranking

router = APIRouter(tags=["api"])


# ── Dashboard / Analytics ─────────────────────────────────────────

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return get_general_stats(db)

@router.get("/analytics/daily")
def daily(days: int = 14, db: Session = Depends(get_db)):
    return get_daily_messages(db, days)

@router.get("/analytics/intents")
def intents(days: int = 7, db: Session = Depends(get_db)):
    return get_top_intents(db, days)

@router.get("/analytics/optin-curve")
def optin_curve(days: int = 30, db: Session = Depends(get_db)):
    return get_optin_curve(db, days)

@router.get("/analytics/cities")
def cities(db: Session = Depends(get_db)):
    return get_city_stats(db)

@router.get("/analytics/ambassadors")
def ambassadors(limit: int = 20, db: Session = Depends(get_db)):
    return get_ambassador_ranking(db, limit)


# ── Contactos ─────────────────────────────────────────────────────

@router.get("/contacts/export")
def export_contacts(
    city:     str = "",
    opted_in: str = "",
    group:    str = "",
    search:   str = "",
    db:       Session = Depends(get_db),
):
    """Exporta contactos filtrados a CSV."""
    q = db.query(Contact)
    if city:
        q = q.filter(Contact.city.ilike(f"%{city}%"))
    if opted_in == "true":
        q = q.filter(Contact.opted_in == True)
    elif opted_in == "false":
        q = q.filter(Contact.opted_in == False)
    if search:
        q = q.filter(
            Contact.name.ilike(f"%{search}%") | Contact.phone.contains(search)
        )
    if group:
        try:
            from models.contact_group import ContactGroup
            g = db.query(ContactGroup).filter(ContactGroup.id == int(group)).first()
            if g:
                q = q.filter(Contact.id.in_([m.id for m in g.members]))
        except Exception:
            pass

    contacts = q.order_by(desc(Contact.created_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["phone", "name", "city", "department", "opted_in", "segment", "total_msgs"])
    for c in contacts:
        writer.writerow([
            c.phone, c.name or "", c.city or "", c.department or "",
            "si" if c.opted_in else "no", c.segment, c.total_msgs
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contactos.csv"}
    )


@router.get("/contacts")
def list_contacts(
    page:     int = Query(1, ge=1),
    limit:    int = Query(50, le=200),
    city:     str = "",
    opted_in: str = "",
    segment:  str = "",
    group:    str = "",
    search:   str = "",
    db:       Session = Depends(get_db),
):
    q = db.query(Contact)
    if city:
        q = q.filter(Contact.city.ilike(f"%{city}%"))
    if opted_in == "true":
        q = q.filter(Contact.opted_in == True)
    elif opted_in == "false":
        q = q.filter(Contact.opted_in == False)
    if segment:
        q = q.filter(Contact.segment == segment)
    if search:
        q = q.filter(
            Contact.name.ilike(f"%{search}%") | Contact.phone.contains(search)
        )
    if group:
        try:
            from models.contact_group import ContactGroup
            g = db.query(ContactGroup).filter(ContactGroup.id == int(group)).first()
            if g:
                member_ids = [m.id for m in g.members]
                q = q.filter(Contact.id.in_(member_ids))
        except Exception:
            pass

    total = q.count()
    items = q.order_by(desc(Contact.created_at)).offset((page - 1) * limit).limit(limit).all()

    # Incluir grupos de cada contacto
    result = []
    for c in items:
        d = c.to_dict()
        try:
            d["groups"] = [{"id": g.id, "name": g.name, "color": g.color, "icon": g.icon} for g in c.groups]
        except Exception:
            d["groups"] = []
        result.append(d)

    return {"total": total, "page": page, "contacts": result}


@router.get("/contacts/{phone}")
def get_contact(phone: str, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.phone == phone).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    d = c.to_dict()
    try:
        d["groups"] = [{"id": g.id, "name": g.name, "color": g.color, "icon": g.icon} for g in c.groups]
    except Exception:
        d["groups"] = []
    return d


@router.get("/contacts/{phone}/conversations")
def contact_conversations(phone: str, limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in reversed(rows)]


# ── Crear contacto manual ─────────────────────────────────────────

class ContactIn(BaseModel):
    phone:      str
    name:       str  = ""
    city:       str  = ""
    department: str  = ""
    opted_in:   bool = False


@router.post("/contacts", status_code=201)
def create_contact(body: ContactIn, db: Session = Depends(get_db)):
    """Crea un contacto individual manualmente desde el panel."""
    phone = body.phone.strip().replace(" ", "").replace("+", "").replace("-", "")
    if not phone:
        raise HTTPException(status_code=400, detail="Teléfono obligatorio")
    if not phone.startswith("57"):
        phone = "57" + phone

    existing = db.query(Contact).filter(Contact.phone == phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="El contacto ya existe")

    contact = Contact(
        phone      = phone,
        name       = body.name.strip() or None,
        city       = body.city.strip() or None,
        department = body.department.strip() or None,
        opted_in   = body.opted_in,
        source     = "manual",
        segment    = "general",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact.to_dict()


# ── Actualizar contacto ───────────────────────────────────────────

class ContactUpdate(BaseModel):
    name:       Optional[str]  = None
    city:       Optional[str]  = None
    department: Optional[str]  = None
    opted_in:   Optional[bool] = None
    segment:    Optional[str]  = None


@router.put("/contacts/{phone}")
def update_contact(phone: str, body: ContactUpdate, db: Session = Depends(get_db)):
    """Actualiza datos de un contacto."""
    c = db.query(Contact).filter(Contact.phone == phone).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    if body.name       is not None: c.name       = body.name
    if body.city       is not None: c.city       = body.city
    if body.department is not None: c.department = body.department
    if body.opted_in   is not None:
        c.opted_in = body.opted_in
        if body.opted_in:
            c.opted_in_at = datetime.utcnow()
        else:
            c.opted_out_at = datetime.utcnow()
    if body.segment is not None: c.segment = body.segment
    db.commit()
    db.refresh(c)
    d = c.to_dict()
    try:
        d["groups"] = [{"id": g.id, "name": g.name, "color": g.color, "icon": g.icon} for g in c.groups]
    except Exception:
        d["groups"] = []
    return d


# ── Eliminar contacto ─────────────────────────────────────────────

@router.delete("/contacts/{phone}")
def delete_contact(phone: str, db: Session = Depends(get_db)):
    """Elimina un contacto."""
    c = db.query(Contact).filter(Contact.phone == phone).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Importar CSV inteligente ──────────────────────────────────────

def _clean_phone(raw: str) -> str | None:
    """Limpia y valida un número de teléfono colombiano."""
    p = re.sub(r"[\s\-\(\)\+\.]", "", str(raw)).replace(".0", "")
    if re.match(r"^3\d{9}$", p):
        return "57" + p
    if re.match(r"^57\d{10}$", p):
        return p
    return None


def _detect_phone_column(headers: list[str]) -> str | None:
    """Detecta automáticamente cuál columna tiene los teléfonos."""
    for h in headers:
        hl = h.lower().strip()
        if any(k in hl for k in ["phone", "telefono", "teléfono", "celular", "movil", "móvil", "numero", "número"]):
            return h
    return None


def _detect_name_column(headers: list[str]) -> str | None:
    for h in headers:
        hl = h.lower().strip()
        if any(k in hl for k in ["name", "nombre", "apellido", "contacto"]):
            return h
    return None


def _detect_city_column(headers: list[str]) -> str | None:
    for h in headers:
        hl = h.lower().strip()
        if any(k in hl for k in ["city", "ciudad", "municipio"]):
            return h
    return None


def _detect_dept_column(headers: list[str]) -> str | None:
    for h in headers:
        hl = h.lower().strip()
        if any(k in hl for k in ["department", "departamento", "depto", "dpto"]):
            return h
    return None


@router.post("/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    """
    Importa contactos desde CSV con detección automática de columnas.
    Limpia teléfonos, descarta duplicados y reporta cada caso.
    """
    content = await file.read()

    # Intentar diferentes encodings
    text = None
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(enc)
            break
        except Exception:
            continue
    if not text:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo")

    reader  = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    # Detectar columnas automáticamente
    phone_col = _detect_phone_column(list(headers)) or (headers[0] if headers else None)
    name_col  = _detect_name_column(list(headers))
    city_col  = _detect_city_column(list(headers))
    dept_col  = _detect_dept_column(list(headers))

    created = updated = errors = skipped = 0
    details = []
    seen_phones = set()  # para detectar duplicados dentro del mismo archivo

    for row in reader:
        raw_phone = str(row.get(phone_col or "", "")).strip()
        if not raw_phone:
            errors += 1
            details.append({"phone": raw_phone or "vacío", "status": "error", "reason": "Teléfono vacío"})
            continue

        phone = _clean_phone(raw_phone)
        if not phone:
            errors += 1
            details.append({"phone": raw_phone, "status": "error", "reason": "Formato inválido"})
            continue

        # Duplicado en el mismo archivo
        if phone in seen_phones:
            skipped += 1
            details.append({"phone": phone, "status": "duplicate", "reason": "Duplicado en el archivo"})
            continue
        seen_phones.add(phone)

        name = (row.get(name_col or "", "") or "").strip() or None
        city = (row.get(city_col or "", "") or "").strip() or None
        dept = (row.get(dept_col or "", "") or "").strip() or None

        existing = db.query(Contact).filter(Contact.phone == phone).first()
        if existing:
            # Actualizar solo campos vacíos
            changed = False
            if name and not existing.name:  existing.name = name;  changed = True
            if city and not existing.city:  existing.city = city;  changed = True
            if dept and not existing.department: existing.department = dept; changed = True
            if changed:
                updated += 1
                details.append({"phone": phone, "status": "updated"})
            else:
                skipped += 1
                details.append({"phone": phone, "status": "duplicate", "reason": "Ya existe"})
        else:
            db.add(Contact(
                phone      = phone,
                name       = name,
                city       = city,
                department = dept,
                source     = "import",
                segment    = "general",
            ))
            created += 1
            details.append({"phone": phone, "status": "created"})

    db.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors":  errors,
        "total":   created + updated + skipped + errors,
        "details": details,
    }


# ── Conversaciones ────────────────────────────────────────────────

@router.get("/conversations")
def list_conversations(
    page:  int = Query(1, ge=1),
    limit: int = Query(50, le=100),
    q:     str = "",
    db:    Session = Depends(get_db),
):
    """Último mensaje de cada contacto."""
    subq = (
        db.query(
            Conversation.phone,
            func.max(Conversation.timestamp).label("last_ts"),
        )
        .group_by(Conversation.phone)
        .subquery()
    )
    query = db.query(Conversation).join(
        subq,
        (Conversation.phone == subq.c.phone) &
        (Conversation.timestamp == subq.c.last_ts),
    )
    if q:
        # Buscar también por nombre del contacto
        contact_phones = [
            c.phone for c in db.query(Contact).filter(Contact.name.ilike(f"%{q}%")).all()
        ]
        query = query.filter(
            Conversation.phone.in_(contact_phones) |
            Conversation.phone.contains(q) |
            Conversation.message.ilike(f"%{q}%")
        )

    total = query.count()
    rows  = query.order_by(desc(Conversation.timestamp)).offset((page - 1) * limit).limit(limit).all()

    # Enriquecer con nombre del contacto
    result = []
    for r in rows:
        d = r.to_dict()
        contact = db.query(Contact).filter(Contact.phone == r.phone).first()
        d["contact_name"] = contact.name if contact else None
        result.append(d)

    return {"total": total, "items": result}


@router.delete("/conversations/cleanup")
def cleanup_conversations(days: int = 30, db: Session = Depends(get_db)):
    """Elimina conversaciones más antiguas que X días."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(Conversation).filter(Conversation.timestamp < cutoff).delete()
    db.commit()
    return {"deleted": deleted, "cutoff_days": days}


# ── Chat de prueba ────────────────────────────────────────────────

class ChatTestIn(BaseModel):
    phone:   str
    message: str


@router.post("/chat-test")
async def chat_test(body: ChatTestIn, db: Session = Depends(get_db)):
    """Prueba el bot directamente desde el panel sin necesitar WhatsApp."""
    phone   = body.phone.strip()
    message = body.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    contact = db.query(Contact).filter(Contact.phone == phone).first()
    if not contact:
        contact = Contact(phone=phone, name="Prueba Panel", source="panel")
        db.add(contact)
        db.commit()
        db.refresh(contact)

    history_rows = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.timestamp.desc())
        .limit(10)
        .all()
    )
    history = [{"role": r.role, "content": r.message} for r in reversed(history_rows)]

    from services.ai import process_message, detect_intent
    intent = detect_intent(message)
    db.add(Conversation(phone=phone, role="user", message=message, intent=intent))
    contact.total_msgs = (contact.total_msgs or 0) + 1
    contact.last_seen  = datetime.utcnow()
    db.commit()

    reply, detected_intent = await process_message(
        phone=        phone,
        message=      message,
        history=      history,
        contact_name= "Usuario Panel",
    )

    db.add(Conversation(phone=phone, role="assistant", message=reply, intent=detected_intent))
    db.commit()

    return {"reply": reply, "intent": detected_intent}