# 📄 backend/routers/heygen.py  ← ARCHIVO NUEVO
"""
Endpoints para generación de videos con HeyGen.
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from config import get_settings

log     = logging.getLogger("abelardo_bot")
router  = APIRouter(prefix="/heygen", tags=["heygen"])
settings = get_settings()

HEYGEN_API = "https://api.heygen.com/v2"


class GenerateIn(BaseModel):
    text:       str
    background: str = "campana"


@router.post("/generate")
async def generate_video(body: GenerateIn):
    """Genera un video con el avatar usando HeyGen API."""
    if not settings.HEYGEN_API_KEY:
        raise HTTPException(status_code=400, detail="HEYGEN_API_KEY no configurada en Render → Environment")

    if not settings.HEYGEN_AVATAR_ID:
        raise HTTPException(status_code=400, detail="HEYGEN_AVATAR_ID no configurada en Render → Environment")

    # Mapeo de fondos a colores/IDs de HeyGen
    bg_map = {
        "debate":   "#1e3a5f",
        "campana":  "#8B0000",
        "congreso": "#1a2a1a",
        "neutro":   "#1a1a1a",
    }
    bg_color = bg_map.get(body.background, "#8B0000")

    payload = {
        "video_inputs": [{
            "character": {
                "type":      "avatar",
                "avatar_id": settings.HEYGEN_AVATAR_ID,
                "scale":     1.0,
            },
            "voice": {
                "type":     "text",
                "input_text": body.text,
                "voice_id": "es-CO-SalomeNeural",  # voz colombiana
            },
            "background": {
                "type":  "color",
                "value": bg_color,
            }
        }],
        "dimension": {"width": 720, "height": 1280},  # vertical para WhatsApp
        "aspect_ratio": "9:16",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{HEYGEN_API}/video/generate",
            headers={
                "X-Api-Key":    settings.HEYGEN_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if r.status_code != 200:
            log.error(f"HeyGen error: {r.text}")
            raise HTTPException(status_code=400, detail=f"HeyGen error: {r.text}")

        data = r.json()
        video_id = data.get("data", {}).get("video_id")
        if not video_id:
            raise HTTPException(status_code=400, detail="No se obtuvo video_id de HeyGen")

        log.info(f"HeyGen video generando: {video_id}")
        return {"video_id": video_id, "status": "processing"}


@router.get("/status/{video_id}")
async def video_status(video_id: str):
    """Verifica el estado de un video en HeyGen."""
    if not settings.HEYGEN_API_KEY:
        raise HTTPException(status_code=400, detail="HEYGEN_API_KEY no configurada")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{HEYGEN_API}/video/{video_id}",
            headers={"X-Api-Key": settings.HEYGEN_API_KEY},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Error al consultar HeyGen")

        data      = r.json().get("data", {})
        status    = data.get("status", "processing")
        video_url = data.get("video_url", "")

        return {"status": status, "video_url": video_url, "video_id": video_id}