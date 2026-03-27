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