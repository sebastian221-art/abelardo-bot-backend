# 📄 backend/services/whatsapp.py
import httpx
import logging
from config import get_settings

settings = get_settings()
log      = logging.getLogger("abelardo_bot")

BASE_URL = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_ID}/messages"
HEADERS  = {
    "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    "Content-Type":  "application/json",
}


async def _post(payload: dict) -> bool:
    """Envía cualquier payload a la API de WhatsApp."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(BASE_URL, headers=HEADERS, json=payload)
        if r.status_code == 200:
            return True
        log.error(f"WhatsApp API error {r.status_code}: {r.text}")
        return False


async def send_text(to: str, message: str) -> bool:
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "text",
        "text":              {"body": message, "preview_url": False},
    })


async def send_template(to: str, name: str, image_url: str = "", param: str = "") -> bool:
    """
    Envía una plantilla aprobada por Meta.
    - name:      nombre de la plantilla (ej: bienvenida_campana)
    - image_url: URL pública de la imagen del encabezado (opcional)
    - param:     valor del {{1}} en el cuerpo (nombre del contacto)
    """
    components = []

    # Encabezado con imagen
    if image_url:
        components.append({
            "type": "header",
            "parameters": [{
                "type":  "image",
                "image": {"link": image_url}
            }]
        })

    # Cuerpo con variable {{1}}
    if param:
        components.append({
            "type": "body",
            "parameters": [{
                "type": "text",
                "text": param
            }]
        })

    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "template",
        "template": {
            "name":      name,
            "language":  {"code": "es"},
            "components": components
        }
    })


async def send_image(to: str, image_url: str, caption: str = "") -> bool:
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "image",
        "image":             {"link": image_url, "caption": caption},
    })


async def send_audio(to: str, audio_url: str) -> bool:
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "audio",
        "audio":             {"link": audio_url},
    })


async def send_document(to: str, doc_url: str, filename: str = "documento.pdf") -> bool:
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "document",
        "document":          {"link": doc_url, "filename": filename},
    })


async def mark_read(message_id: str) -> bool:
    return await _post({
        "messaging_product": "whatsapp",
        "status":            "read",
        "message_id":        message_id,
    })