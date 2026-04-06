# 📄 backend/services/broadcast.py  ← REEMPLAZA EL ANTERIOR
"""
Motor de envíos masivos (broadcasts).
Soporta texto libre y plantillas aprobadas por Meta.
Al reanudar, salta los contactos que ya recibieron el mensaje.
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

SEND_DELAY = 0.8   # segundos entre mensajes


async def execute_broadcast(db: Session, broadcast_id: int) -> dict:
    """
    Ejecuta un broadcast.
    Si fue pausado previamente, retoma desde donde quedó
    saltando los contactos que ya fueron procesados.
    """
    broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not broadcast:
        raise ValueError(f"Broadcast {broadcast_id} no existe")

    if broadcast.status not in ("draft", "scheduled", "sending", "paused"):
        raise ValueError(f"Broadcast ya fue enviado (estado: {broadcast.status})")

    # Validación: plantilla requiere imagen
    if broadcast.template_name and not broadcast.media_url:
        broadcast.status = "failed"
        db.commit()
        raise ValueError(
            f"La plantilla '{broadcast.template_name}' requiere una imagen en el encabezado."
        )

    # ── Obtener todos los contactos del segmento ──────────────────
    contacts: list[Contact] = get_contacts_for_broadcast(
        db, broadcast.segment, broadcast.segment_value or ""
    )

    # ── Obtener teléfonos que YA fueron procesados (enviados O fallidos) ──
    already_processed = set(
        row.phone for row in
        db.query(BroadcastLog.phone)
        .filter(BroadcastLog.broadcast_id == broadcast_id)
        .all()
    )

    # ── Filtrar solo los que faltan ───────────────────────────────
    pending = [c for c in contacts if c.phone not in already_processed]

    log.info(
        f"Broadcast {broadcast_id}: {len(contacts)} total, "
        f"{len(already_processed)} ya procesados, "
        f"{len(pending)} pendientes"
    )

    broadcast.status        = "sending"
    broadcast.total_targets = len(contacts)  # total real siempre
    db.commit()

    # Recuperar contadores previos
    sent   = broadcast.sent_count   or 0
    failed = broadcast.failed_count or 0

    for contact in pending:
        # Verificar si fue pausado durante el envío
        current = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
        if current and current.status == "paused":
            log.info(f"Broadcast {broadcast_id} pausado — procesados hasta ahora: {sent + failed}/{len(contacts)}")
            broadcast.sent_count   = sent
            broadcast.failed_count = failed
            db.commit()
            return {"sent": sent, "failed": failed, "total": len(contacts), "paused": True}

        success = False
        error   = None

        try:
            if broadcast.template_name:
                success = await send_template(
                    to        = contact.phone,
                    name      = broadcast.template_name,
                    image_url = broadcast.media_url or "",
                    param     = contact.name or "Defensor",
                )
            elif broadcast.media_type == "image" and broadcast.media_url:
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

        # Actualizar progreso cada 10 envíos
        if (sent + failed) % 10 == 0:
            broadcast.sent_count   = sent
            broadcast.failed_count = failed
            db.commit()

        await asyncio.sleep(SEND_DELAY)

    # Finalizado
    broadcast.status       = "sent"
    broadcast.sent_count   = sent
    broadcast.failed_count = failed
    broadcast.sent_at      = broadcast.sent_at or datetime.utcnow()
    db.commit()

    log.info(f"Broadcast {broadcast_id} completado — enviados: {sent}, fallidos: {failed}")
    return {"sent": sent, "failed": failed, "total": len(contacts)}


def create_broadcast(
    db:            Session,
    title:         str,
    message:       str,
    segment:       str             = "todos",
    segment_value: str             = "",
    media_url:     str             = "",
    media_type:    str             = "",
    template_name: str             = "",
    scheduled_at:  datetime | None = None,
    created_by:    str             = "admin",
) -> Broadcast:
    b = Broadcast(
        title         = title,
        message       = message,
        segment       = segment,
        segment_value = segment_value or None,
        media_url     = media_url or None,
        media_type    = media_type or None,
        template_name = template_name or None,
        status        = "scheduled" if scheduled_at else "draft",
        scheduled_at  = scheduled_at,
        created_by    = created_by,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b