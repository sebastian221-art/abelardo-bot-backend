# 📄 backend/services/broadcast.py
"""
Motor de envíos masivos (broadcasts).
Soporta texto libre y plantillas aprobadas por Meta.
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from models.broadcast      import Broadcast
from models.broadcast_log  import BroadcastLog
from models.contact        import Contact
from services.whatsapp     import send_text, send_image, send_audio, send_document, send_template
from services.segmentation import get_contacts_for_broadcast

log = logging.getLogger("abelardo_bot")

SEND_DELAY = 0.8   # segundos entre mensajes para no saturar la API


async def execute_broadcast(db: Session, broadcast_id: int) -> dict:
    """
    Ejecuta un broadcast.
    Si el campo template_name está definido usa plantilla aprobada por Meta.
    Si no, usa texto libre (solo funciona con contactos que ya escribieron primero).
    """
    broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not broadcast:
        raise ValueError(f"Broadcast {broadcast_id} no existe")

    if broadcast.status not in ("draft", "scheduled"):
        raise ValueError(f"Broadcast ya fue enviado (estado: {broadcast.status})")

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
            # ── Usar plantilla aprobada (para broadcasts masivos) ──
            if hasattr(broadcast, "template_name") and broadcast.template_name:
                success = await send_template(
                    to        = contact.phone,
                    name      = broadcast.template_name,
                    image_url = broadcast.media_url or "",
                    param     = contact.name or "Defensor",
                )

            # ── Mensaje con imagen ─────────────────────────────────
            elif broadcast.media_type == "image" and broadcast.media_url:
                success = await send_image(contact.phone, broadcast.media_url, broadcast.message)

            # ── Mensaje con audio ──────────────────────────────────
            elif broadcast.media_type == "audio" and broadcast.media_url:
                success = await send_audio(contact.phone, broadcast.media_url)

            # ── Mensaje con documento ──────────────────────────────
            elif broadcast.media_type == "document" and broadcast.media_url:
                success = await send_document(contact.phone, broadcast.media_url)

            # ── Texto libre ────────────────────────────────────────
            else:
                success = await send_text(contact.phone, broadcast.message)

        except Exception as e:
            error   = str(e)
            success = False

        db.add(BroadcastLog(
            broadcast_id = broadcast.id,
            phone        = contact.phone,
            status       = "sent" if success else "failed",
            error        = error,
            sent_at      = datetime.utcnow() if success else None,
        ))

        if success:
            sent += 1
        else:
            failed += 1
            log.warning(f"Broadcast {broadcast_id}: fallo → {contact.phone} — {error}")

        if (sent + failed) % 10 == 0:
            broadcast.sent_count   = sent
            broadcast.failed_count = failed
            db.commit()

        await asyncio.sleep(SEND_DELAY)

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
    segment:       str            = "todos",
    segment_value: str            = "",
    media_url:     str            = "",
    media_type:    str            = "",
    template_name: str            = "",
    scheduled_at:  datetime | None = None,
    created_by:    str            = "admin",
) -> Broadcast:
    b = Broadcast(
        title          = title,
        message        = message,
        segment        = segment,
        segment_value  = segment_value or None,
        media_url      = media_url or None,
        media_type     = media_type or None,
        template_name  = template_name or None,
        status         = "scheduled" if scheduled_at else "draft",
        scheduled_at   = scheduled_at,
        created_by     = created_by,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b