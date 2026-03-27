# 📄 backend/routers/api.py  ← REEMPLAZA EL ANTERIOR
"""
Endpoints generales del panel: contactos, conversaciones, stats, chat-test.
"""
import csv
import io
from datetime    import datetime
from fastapi     import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic    import BaseModel
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

@router.get("/contacts")
def list_contacts(
    page:     int = Query(1, ge=1),
    limit:    int = Query(50, le=200),
    city:     str = "",
    opted_in: str = "",
    segment:  str = "",
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

    total = q.count()
    items = q.order_by(desc(Contact.created_at)).offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "page": page, "contacts": [c.to_dict() for c in items]}


@router.get("/contacts/{phone}")
def get_contact(phone: str, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.phone == phone).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return c.to_dict()


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
    phone = body.phone.strip().replace(" ", "").replace("+", "")
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


# ── Importar CSV ──────────────────────────────────────────────────

@router.post("/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    """Importa contactos desde CSV. Columnas: phone, name, city, department"""
    content = await file.read()
    text    = content.decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(text))

    created = updated = errors = 0

    for row in reader:
        phone = str(row.get("phone", "")).strip().replace(" ", "").replace("+", "")
        if not phone:
            errors += 1
            continue
        if not phone.startswith("57"):
            phone = "57" + phone

        existing = db.query(Contact).filter(Contact.phone == phone).first()
        if existing:
            if row.get("name") and not existing.name:
                existing.name = row["name"].strip()
            if row.get("city") and not existing.city:
                existing.city = row["city"].strip()
            if row.get("department") and not existing.department:
                existing.department = row["department"].strip()
            updated += 1
        else:
            db.add(Contact(
                phone=      phone,
                name=       row.get("name", "").strip() or None,
                city=       row.get("city", "").strip() or None,
                department= row.get("department", "").strip() or None,
                source=     "import",
            ))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


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
        query = query.filter(
            Conversation.phone.contains(q) | Conversation.message.ilike(f"%{q}%")
        )

    total = query.count()
    rows  = query.order_by(desc(Conversation.timestamp)).offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "items": [r.to_dict() for r in rows]}


# ── Chat de prueba ────────────────────────────────────────────────

class ChatTestIn(BaseModel):
    phone:   str
    message: str


@router.post("/chat-test")
async def chat_test(body: ChatTestIn, db: Session = Depends(get_db)):
    """
    Prueba el bot directamente desde el panel sin necesitar WhatsApp.
    """
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