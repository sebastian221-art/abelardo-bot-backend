# 📄 backend/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME:              str  = "ChatBot Abelardo 2026"
    DEBUG:                 bool = True
    DATABASE_URL:          str  = "sqlite:///./abelardo.db"
    SECRET_KEY:            str  = "cambia_esto_en_produccion"

    # WhatsApp
    WHATSAPP_TOKEN:        str  = ""
    WHATSAPP_PHONE_ID:     str  = ""
    WEBHOOK_VERIFY_TOKEN:  str  = "abelardo2026_verify"

    # Groq
    GROQ_API_KEY:          str  = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()