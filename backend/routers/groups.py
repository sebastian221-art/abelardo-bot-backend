# 📄 backend/routers/groups.py  ← ARCHIVO NUEVO
"""
Endpoints para grupos personalizados de contactos.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database     import get_db
from models.contact      import Contact
from models.contact_group import ContactGroup

log    = logging.getLogger("abelardo_bot")
router = APIRouter(prefix="/groups", tags=["groups"])


class GroupIn(BaseModel):
    name:        str
    description: str  = ""
    color:       str  = "#6366f1"
    icon:        str  = "👥"


class AddMembersIn(BaseModel):
    phones: List[str]


# ── CRUD grupos ───────────────────────────────────────────────────

@router.get("/")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(ContactGroup).all()
    return [g.to_dict() for g in groups]


@router.post("/", status_code=201)
def create_group(body: GroupIn, db: Session = Depends(get_db)):
    existing = db.query(ContactGroup).filter(ContactGroup.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un grupo con ese nombre")
    g = ContactGroup(
        name        = body.name,
        description = body.description,
        color       = body.color,
        icon        = body.icon,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    log.info(f"Grupo creado: {g.name}")
    return g.to_dict()


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    g = db.query(ContactGroup).filter(ContactGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    db.delete(g)
    db.commit()
    return {"ok": True}


# ── Miembros ──────────────────────────────────────────────────────

@router.post("/{group_id}/members")
def add_members(group_id: int, body: AddMembersIn, db: Session = Depends(get_db)):
    """Agrega contactos al grupo por teléfono."""
    g = db.query(ContactGroup).filter(ContactGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    added = 0
    not_found = []
    for phone in body.phones:
        phone = phone.strip().replace("+", "")
        if not phone.startswith("57"):
            phone = "57" + phone
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        if contact and contact not in g.members:
            g.members.append(contact)
            added += 1
        elif not contact:
            not_found.append(phone)

    db.commit()
    return {"added": added, "not_found": not_found, "total": len(g.members)}


@router.delete("/{group_id}/members/{phone}")
def remove_member(group_id: int, phone: str, db: Session = Depends(get_db)):
    g = db.query(ContactGroup).filter(ContactGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    contact = db.query(Contact).filter(Contact.phone == phone).first()
    if contact and contact in g.members:
        g.members.remove(contact)
        db.commit()
    return {"ok": True}


@router.get("/{group_id}/members")
def list_members(group_id: int, db: Session = Depends(get_db)):
    g = db.query(ContactGroup).filter(ContactGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return [c.to_dict() for c in g.members]