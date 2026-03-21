# 📄 backend/routers/knowledge.py
"""
CRUD de la Base de Conocimiento del bot.
GET    /knowledge/           → listar documentos
POST   /knowledge/           → crear documento
PUT    /knowledge/{id}       → editar documento
DELETE /knowledge/{id}       → eliminar documento
PATCH  /knowledge/{id}/toggle → activar / desactivar
GET    /knowledge/categories  → lista de categorías disponibles
"""
from datetime import datetime
from typing   import Optional
from fastapi  import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database  import get_db
from models.knowledge import KnowledgeDoc

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

CATEGORIES = [
    "quién es abelardo",
    "seguridad",
    "economía",
    "salud",
    "educación",
    "campo",
    "energía",
    "corrupción",
    "familia y valores",
    "propuestas generales",
    "frases y discursos",
    "preguntas frecuentes",
    "contexto colombia",
    "campaña",
]


class DocIn(BaseModel):
    title:    str
    category: str
    content:  str
    active:   Optional[bool] = True


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/categories")
def get_categories():
    return CATEGORIES


@router.get("/")
def list_docs(
    category: str = "",
    active:   str = "",
    db:       Session = Depends(get_db),
):
    q = db.query(KnowledgeDoc)
    if category:
        q = q.filter(KnowledgeDoc.category == category)
    if active == "true":
        q = q.filter(KnowledgeDoc.active == True)
    elif active == "false":
        q = q.filter(KnowledgeDoc.active == False)
    docs = q.order_by(KnowledgeDoc.category, KnowledgeDoc.title).all()
    return [d.to_dict() for d in docs]


@router.post("/", status_code=201)
def create_doc(body: DocIn, db: Session = Depends(get_db)):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="El título es obligatorio")
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="El contenido es obligatorio")

    doc = KnowledgeDoc(
        title=    body.title.strip(),
        category= body.category.strip(),
        content=  body.content.strip(),
        active=   body.active,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc.to_dict()


@router.put("/{doc_id}")
def update_doc(doc_id: int, body: DocIn, db: Session = Depends(get_db)):
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc.title      = body.title.strip()
    doc.category   = body.category.strip()
    doc.content    = body.content.strip()
    doc.active     = body.active
    doc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    return doc.to_dict()


@router.patch("/{doc_id}/toggle")
def toggle_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    doc.active     = not doc.active
    doc.updated_at = datetime.utcnow()
    db.commit()
    return {"id": doc.id, "active": doc.active}


@router.delete("/{doc_id}")
def delete_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    db.delete(doc)
    db.commit()
    return {"ok": True, "deleted": doc_id}