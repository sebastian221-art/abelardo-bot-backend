# 📄 backend/routers/broadcast.py  ← REEMPLAZA EL ANTERIOR
"""
Endpoints de broadcasts (envíos masivos).
POST /broadcast/            → crear broadcast
GET  /broadcast/            → listar broadcasts
GET  /broadcast/{id}        → detalle
POST /broadcast/{id}/send   → ejecutar envío
POST /broadcast/{id}/cancel → cancelar
GET  /broadcast/{id}/logs   → logs de envío
GET  /broadcast/preview     → cuántos contactos recibirían el mensaje
"""
import asyncio
import logging
from datetime import datetime
from typing   import Optional
from fastapi  import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy     import desc

from models.database       import get_db
from models.broadcast      import Broadcast
from models.broadcast_log  import BroadcastLog
from services.broadcast    import create_broadcast, execute_broadcast
from services.segmentation import count_contacts_for_broadcast

log    = logging.getLogger("abelardo_bot")
router = APIRouter(prefix="/broadcast", tags=["broadcast"])


# ── Schema ────────────────────────────────────────────────────────

class BroadcastIn(BaseModel):
    title:          str
    message:        str  = ""
    segment:        str  = "todos"
    segment_value:  Optional[str] = ""
    media_url:      Optional[str] = ""
    media_type:     Optional[str] = ""
    template_name:  Optional[str] = ""   # ← nombre de plantilla aprobada
    scheduled_at:   Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/preview")
def preview_broadcast(
    segment:       str = "todos",
    segment_value: str = "",
    db:            Session = Depends(get_db),
):
    count = count_contacts_for_broadcast(db, segment, segment_value)
    return {"segment": segment, "segment_value": segment_value, "total_targets": count}


@router.post("/", status_code=201)
def create(body: BroadcastIn, db: Session = Depends(get_db)):
    scheduled = None
    if body.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(body.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa ISO 8601.")

    b = create_broadcast(
        db            = db,
        title         = body.title,
        message       = body.message or "",
        segment       = body.segment,
        segment_value = body.segment_value or "",
        media_url     = body.media_url or "",
        media_type    = body.media_type or "",
        template_name = body.template_name or "",
        scheduled_at  = scheduled,
    )
    return b.to_dict()


@router.get("/")
def list_broadcasts(
    page:   int = 1,
    limit:  int = 20,
    status: str = "",
    db:     Session = Depends(get_db),
):
    q = db.query(Broadcast)
    if status:
        q = q.filter(Broadcast.status == status)
    total = q.count()
    items = q.order_by(desc(Broadcast.created_at)).offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "page": page, "items": [b.to_dict() for b in items]}


@router.get("/{broadcast_id}")
def get_broadcast(broadcast_id: int, db: Session = Depends(get_db)):
    b = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    return b.to_dict()


@router.post("/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id:     int,
    background_tasks: BackgroundTasks,
    db:               Session = Depends(get_db),
):
    b = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    if b.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail=f"No se puede enviar: estado '{b.status}'")

    background_tasks.add_task(_run_broadcast, broadcast_id)
    log.info(f"📤  Broadcast {broadcast_id} encolado para envío")
    return {"ok": True, "message": "Envío iniciado", "broadcast_id": broadcast_id}


async def _run_broadcast(broadcast_id: int):
    from models.database import SessionLocal
    db = SessionLocal()
    try:
        stats = await execute_broadcast(db, broadcast_id)
        log.info(f"✅  Broadcast {broadcast_id} finalizado: {stats}")
    except Exception as e:
        log.error(f"✗  Error en broadcast {broadcast_id}: {e}")
    finally:
        db.close()


@router.post("/{broadcast_id}/cancel")
def cancel_broadcast(broadcast_id: int, db: Session = Depends(get_db)):
    b = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    if b.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Solo se pueden cancelar borradores o programados")
    b.status = "cancelled"
    db.commit()
    return {"ok": True, "broadcast_id": broadcast_id}


@router.get("/{broadcast_id}/logs")
def broadcast_logs(
    broadcast_id: int,
    page:         int = 1,
    limit:        int = 100,
    status:       str = "",
    db:           Session = Depends(get_db),
):
    q = db.query(BroadcastLog).filter(BroadcastLog.broadcast_id == broadcast_id)
    if status:
        q = q.filter(BroadcastLog.status == status)
    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "items": [i.to_dict() for i in items]}
# ── AGREGAR AL FINAL de backend/routers/broadcast.py ─────────────

@router.post("/{broadcast_id}/pause")
def pause_broadcast(broadcast_id: int, db: Session = Depends(get_db)):
    """Pausa un broadcast en curso."""
    b = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    if b.status != "sending":
        raise HTTPException(status_code=400, detail="Solo se puede pausar un broadcast en envío")
    b.status = "paused"
    db.commit()
    return {"ok": True, "broadcast_id": broadcast_id}


@router.post("/{broadcast_id}/resume")
def resume_broadcast(
    broadcast_id:     int,
    background_tasks: BackgroundTasks,
    db:               Session = Depends(get_db),
):
    """Reanuda un broadcast pausado."""
    b = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    if b.status != "paused":
        raise HTTPException(status_code=400, detail="Solo se puede reanudar un broadcast pausado")
    b.status = "sending"
    db.commit()
    background_tasks.add_task(_run_broadcast, broadcast_id)
    return {"ok": True, "message": "Broadcast reanudado", "broadcast_id": broadcast_id}


@router.post("/{broadcast_id}/duplicate")
def duplicate_broadcast(broadcast_id: int, db: Session = Depends(get_db)):
    """Duplica un broadcast existente como nuevo borrador."""
    original = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")

    nuevo = Broadcast(
        title         = f"{original.title} (copia)",
        message       = original.message,
        template_name = original.template_name,
        segment       = original.segment,
        segment_value = original.segment_value,
        media_url     = original.media_url,
        media_type    = original.media_type,
        status        = "draft",
        created_by    = original.created_by,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    log.info(f"Broadcast {broadcast_id} duplicado → {nuevo.id}")
    return nuevo.to_dict()
# ── AGREGAR AL FINAL de backend/routers/broadcast.py ─────────────

@router.get("/{broadcast_id}/survey-results")
def survey_results(broadcast_id: int, db: Session = Depends(get_db)):
    """
    Analiza las respuestas recibidas de una encuesta.
    Busca mensajes de usuarios que respondieron con 1, 2, 3, 4 o 5
    después de que se envió el broadcast.
    """
    from models.conversation import Conversation
    from models.broadcast_log import BroadcastLog
    import re

    broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")

    # Extraer opciones del mensaje
    lines = (broadcast.message or "").split("\n")
    opciones = []
    for line in lines:
        line = line.strip()
        if re.match(r'^[1-5]️⃣', line) or re.match(r'^[1-5]\s', line):
            # Limpiar el emoji del número
            clean = re.sub(r'^[1-5]️⃣\s*', '', line).strip()
            clean = re.sub(r'^[1-5]\s+', '', clean).strip()
            if clean:
                opciones.append(clean)

    if not opciones:
        return []

    # Teléfonos que recibieron el broadcast
    phones = [
        log.phone for log in
        db.query(BroadcastLog)
        .filter(BroadcastLog.broadcast_id == broadcast_id, BroadcastLog.status == "sent")
        .all()
    ]

    if not phones or not broadcast.sent_at:
        return []

    # Buscar respuestas numéricas después del envío
    counts = [0] * len(opciones)
    total  = 0

    responses = (
        db.query(Conversation)
        .filter(
            Conversation.phone.in_(phones),
            Conversation.role == "user",
            Conversation.timestamp >= broadcast.sent_at,
        )
        .all()
    )

    for r in responses:
        msg = (r.message or "").strip()
        # Detectar respuesta numérica (1, 2, 3, etc.)
        match = re.match(r'^([1-5])\b', msg)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(opciones):
                counts[idx] += 1
                total += 1

    total = total or 1  # evitar división por cero
    return [
        {
            "option":  op,
            "count":   counts[i],
            "percent": round((counts[i] / total) * 100),
        }
        for i, op in enumerate(opciones)
    ]