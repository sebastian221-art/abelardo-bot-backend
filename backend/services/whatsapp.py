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
    msg_type = payload.get("type", "?")
    to       = payload.get("to", "?")
    log.info(f"WA→ tipo={msg_type} destino={to}")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(BASE_URL, headers=HEADERS, json=payload)

    # Loguear SIEMPRE la respuesta completa de Meta
    log.info(f"WA← status={r.status_code} | body={r.text[:500]}")

    if r.status_code == 200:
        try:
            data = r.json()
            if "error" in data:
                log.error(f"WA error en body 200: {data['error']}")
                return False
            ids = [m.get("id","?") for m in data.get("messages", [])]
            log.info(f"WA✓ mensaje aceptado por Meta | message_ids={ids}")
        except Exception as e:
            log.warning(f"WA no pudo parsear body: {e}")
        return True

    log.error(f"WA✗ error {r.status_code}: {r.text}")
    return False


async def send_text(to: str, message: str) -> bool:
    log.info(f"send_text → {to} | '{message[:80]}'")
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "text",
        "text":              {"body": message, "preview_url": False},
    })


async def send_template(to: str, name: str, image_url: str = "", param: str = "") -> bool:
    log.info(f"send_template → {to} | template='{name}' | image='{image_url[:60]}' | param='{param}'")
    components = []

    if image_url:
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"link": image_url}}]
        })

    if param:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": param}]
        })

    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "template",
        "template": {
            "name":       name,
            "language":   {"code": "es"},
            "components": components,
        }
    })


async def send_image(to: str, image_url: str, caption: str = "") -> bool:
    log.info(f"send_image → {to} | url='{image_url[:80]}'")
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "image",
        "image":             {"link": image_url, "caption": caption},
    })


async def send_video(to: str, video_url: str, caption: str = "") -> bool:
    log.info(f"send_video → {to} | url='{video_url[:80]}'")
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "video",
        "video":             {"link": video_url, "caption": caption},
    })


async def send_audio(to: str, audio_url: str) -> bool:
    log.info(f"send_audio → {to} | url='{audio_url[:80]}'")
    return await _post({
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "audio",
        "audio":             {"link": audio_url},
    })


async def send_document(to: str, doc_url: str, filename: str = "documento.pdf") -> bool:
    log.info(f"send_document → {to} | url='{doc_url[:80]}'")
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