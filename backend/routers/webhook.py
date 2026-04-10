# 📄 backend/routers/webhook.py
"""
Webhook de WhatsApp Cloud API.
GET  /webhook → verificación Meta
POST /webhook → procesamiento de mensajes entrantes
Soporta: text, button (botón de plantilla), interactive
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from config              import get_settings
from models.database     import get_db
from models.contact      import Contact
from models.conversation import Conversation
from services.ai         import process_message, detect_intent
from services.whatsapp   import send_text, mark_read

settings = get_settings()
log      = logging.getLogger("abelardo_bot")
router   = APIRouter(tags=["webhook"])


def _extract_message(body: dict) -> tuple[str, str, str, str] | None:
    """
    Extrae (phone, name, text, message_id) del payload de Meta.
    Soporta: text, button (quick reply de plantilla), interactive.
    Loguea el payload completo para diagnóstico.
    """
    try:
        entry   = body["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]

        # Notificación de estado (delivered, read, sent, failed)
        if "messages" not in value:
            statuses = value.get("statuses", [])
            if statuses:
                st = statuses[0]
                log.info(
                    f"WA status update → "
                    f"msg_id={st.get('id')} "
                    f"status={st.get('status')} "
                    f"to={st.get('recipient_id')} "
                    f"timestamp={st.get('timestamp')}"
                )
            else:
                log.info(f"WA payload sin mensajes: {json.dumps(value)[:200]}")
            return None

        msg      = value["messages"][0]
        meta     = value["contacts"][0]
        phone    = msg["from"]
        name     = meta.get("profile", {}).get("name", "")
        msg_type = msg.get("type", "unknown")
        mid      = msg["id"]

        log.info(f"WA← tipo={msg_type} | de={phone} | name='{name}' | msg_id={mid}")

        # ── Texto libre ───────────────────────────────────────────
        if msg_type == "text":
            text = msg["text"]["body"].strip()
            log.info(f"WA← texto: '{text[:100]}'")
            return phone, name, text, mid

        # ── Botón de plantilla (quick reply) ──────────────────────
        if msg_type == "button":
            text = msg["button"]["text"].strip()
            log.info(f"WA← botón de plantilla: '{text}'")
            return phone, name, text, mid

        # ── Respuesta interactiva (list/button reply) ─────────────
        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype       = interactive.get("type", "")
            if itype == "button_reply":
                text = interactive["button_reply"]["title"].strip()
            elif itype == "list_reply":
                text = interactive["list_reply"]["title"].strip()
            else:
                text = json.dumps(interactive)[:100]
            log.info(f"WA← interactive tipo={itype}: '{text}'")
            return phone, name, text, mid

        # ── Otros tipos (imagen, audio, video, sticker, etc.) ─────
        log.info(f"WA← tipo no manejado: {msg_type} — payload={json.dumps(msg)[:200]}")
        return None

    except (KeyError, IndexError) as e:
        log.warning(f"WA← payload inesperado: {e} | body={json.dumps(body)[:300]}")
        return None


@router.get("/webhook")
def verify_webhook(request: Request):
    """Verificación inicial de Meta."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.WEBHOOK_VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """Recibe y procesa mensajes de WhatsApp."""
    body = await request.json()

    extracted = _extract_message(body)
    if not extracted:
        return {"ok": True}

    phone, name, text, message_id = extracted

    log.info(f"📨  [{phone}] {name or 'desconocido'}: {text[:60]}")

    # Marcar como leído
    await mark_read(message_id)

    # ── Obtener o crear contacto ──────────────────────────────────
    contact = db.query(Contact).filter(Contact.phone == phone).first()
    if not contact:
        contact = Contact(phone=phone, name=name or None)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        log.info(f"  ✨  Nuevo contacto: {phone}")

    # Actualizar nombre y actividad
    if name and not contact.name:
        contact.name = name
    contact.total_msgs = (contact.total_msgs or 0) + 1
    contact.last_seen  = datetime.utcnow()
    db.commit()

    # ── Guardar mensaje del usuario ───────────────────────────────
    intent = detect_intent(text)
    db.add(Conversation(phone=phone, role="user", message=text, intent=intent))
    db.commit()

    # ── Manejar OPT-IN / OPT-OUT ─────────────────────────────────
    if intent == "optin" and not contact.opted_in:
        contact.opted_in    = True
        contact.opted_in_at = datetime.utcnow()
        db.commit()
        log.info(f"  ✅  Opt-in: {phone}")

    elif intent == "optout" and contact.opted_in:
        contact.opted_in     = False
        contact.opted_out_at = datetime.utcnow()
        db.commit()
        log.info(f"  ❌  Opt-out: {phone}")

    # ── Historial reciente para contexto ─────────────────────────
    history_rows = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.timestamp.desc())
        .limit(10)
        .all()
    )
    history = [
        {"role": r.role, "content": r.message}
        for r in reversed(history_rows)
    ]

    # ── Generar respuesta ─────────────────────────────────────────
    reply, intent = await process_message(
        phone=phone,
        message=text,
        history=history,
        contact_name=contact.name or "",
    )

    # ── Detectar intereses del mensaje ────────────────────────────
    interest_map = {
        "seguridad": "seguridad",
        "economia":  "economia",
        "salud":     "salud",
        "educacion": "educacion",
        "paz":       "paz",
        "corrupcion":"corrupcion",
    }
    if intent in interest_map:
        contact.add_interest(interest_map[intent])
        db.commit()

    # ── Enviar respuesta ──────────────────────────────────────────
    log.info(f"  🤖  Bot → {phone}: '{reply[:80]}'")
    ok = await send_text(phone, reply)

    # ── Guardar respuesta del bot ─────────────────────────────────
    db.add(Conversation(phone=phone, role="assistant", message=reply, intent=intent))
    db.commit()

    return {"ok": True, "sent": ok}