# 📄 backend/services/broadcast.py
"""
Motor de envíos masivos (broadcasts).
Envía mensajes a listas segmentadas de contactos.
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from models.broadcast     import Broadcast
from models.broadcast_log import BroadcastLog
from models.contact       import Contact
from services.whatsapp    import send_text, send_image, send_audio, send_document
from services.segmentation import get_contacts_for_broadcast

log = logging.getLogger("abelardo_bot")

# Delay entre mensajes para no saturar la API (en segundos)
SEND_DELAY = 0.5


async def execute_broadcast(db: Session, broadcast_id: int) -> dict:
    """
    Ejecuta un broadcast: envía el mensaje a todos los contactos del segmento.
    Retorna stats: {sent, failed, total}.
    """
    broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not broadcast:
        raise ValueError(f"Broadcast {broadcast_id} no existe")

    if broadcast.status not in ("draft", "scheduled"):
        raise ValueError(f"Broadcast ya fue enviado (estado: {broadcast.status})")

    # Obtener contactos objetivo
    contacts: list[Contact] = get_contacts_for_broadcast(
        db, broadcast.segment, broadcast.segment_value or ""
    )

    broadcast.status        = "sending"
    broadcast.total_targets = len(contacts)
    db.commit()

    sent = failed = 0

    for contact in contacts:
        success = False
        error   = None

        try:
            if broadcast.media_type == "image" and broadcast.media_url:
                success = await send_image(contact.phone, broadcast.media_url, broadcast.message)
            elif broadcast.media_type == "audio" and broadcast.media_url:
                success = await send_audio(contact.phone, broadcast.media_url)
            elif broadcast.media_type == "document" and broadcast.media_url:
                success = await send_document(contact.phone, broadcast.media_url)
            else:
                success = await send_text(contact.phone, broadcast.message)
        except Exception as e:
            error   = str(e)
            success = False

        # Log individual
        db.add(BroadcastLog(
            broadcast_id=broadcast.id,
            phone=contact.phone,
            status="sent" if success else "failed",
            error=error,
            sent_at=datetime.utcnow() if success else None,
        ))

        if success:
            sent += 1
        else:
            failed += 1
            log.warning(f"Broadcast {broadcast_id}: fallo envío a {contact.phone} — {error}")

        # Actualizar contadores en tiempo real cada 10 envíos
        if (sent + failed) % 10 == 0:
            broadcast.sent_count   = sent
            broadcast.failed_count = failed
            db.commit()

        await asyncio.sleep(SEND_DELAY)

    # Estado final
    broadcast.status       = "sent"
    broadcast.sent_count   = sent
    broadcast.failed_count = failed
    broadcast.sent_at      = datetime.utcnow()
    db.commit()

    log.info(f"Broadcast {broadcast_id} completado — enviados: {sent}, fallidos: {failed}")
    return {"sent": sent, "failed": failed, "total": len(contacts)}


def create_broadcast(
    db:            Session,
    title:         str,
    message:       str,
    segment:       str   = "opted_in",
    segment_value: str   = "",
    media_url:     str   = "",
    media_type:    str   = "",
    scheduled_at:  datetime | None = None,
    created_by:    str   = "admin",
) -> Broadcast:
    """Crea un broadcast en la base de datos."""
    b = Broadcast(
        title=title,
        message=message,
        segment=segment,
        segment_value=segment_value or None,
        media_url=media_url or None,
        media_type=media_type or None,
        status="scheduled" if scheduled_at else "draft",
        scheduled_at=scheduled_at,
        created_by=created_by,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b