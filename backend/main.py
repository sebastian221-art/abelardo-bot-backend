# 📄 backend/main.py  ← REEMPLAZA EL ANTERIOR
import logging, os, sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

for _lib in [
    "sqlalchemy","sqlalchemy.engine","sqlalchemy.engine.Engine",
    "sqlalchemy.pool","sqlalchemy.dialects","sqlalchemy.orm",
    "watchfiles","httpcore","httpx","chromadb","groq",
    "asyncio","uvicorn.access","uvicorn.error","uvicorn",
    "multipart","starlette","passlib",
]:
    logging.getLogger(_lib).setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.CRITICAL)

CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"
RED="\033[31m";  GREY="\033[90m";  BOLD="\033[1m"; RESET="\033[0m"

class _Fmt(logging.Formatter):
    _MAP = {logging.DEBUG:(GREY,"·"), logging.INFO:(CYAN,"›"),
            logging.WARNING:(YELLOW,"⚠"), logging.ERROR:(RED,"✗")}
    def format(self, r):
        c, ic = self._MAP.get(r.levelno, (GREY,"·"))
        return f"{c}  {ic}  {r.getMessage()}{RESET}"

_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(_Fmt())
log = logging.getLogger("abelardo_bot")
log.setLevel(logging.INFO); log.addHandler(_h); log.propagate = False

from config          import get_settings
from models.database import create_tables, SessionLocal
from services.rag    import load_documents_to_rag
from services.auth   import create_default_admin

from routers.webhook   import router as webhook_router
from routers.api       import router as api_router
from routers.broadcast import router as broadcast_router
from routers.auth      import router as auth_router
from routers.knowledge import router as knowledge_router   # ← NUEVO

settings = get_settings()

_SKIP     = {"/health", "/favicon.ico", "/"}
_SKIP_PFX = ("/_next", "/static", "/docs", "/openapi")
_SC = {2: GREEN, 3: CYAN, 4: YELLOW, 5: RED}

async def _log_req(request: Request, call_next):
    path = request.url.path
    if path in _SKIP or any(path.startswith(p) for p in _SKIP_PFX):
        return await call_next(request)
    resp = await call_next(request)
    sc   = resp.status_code
    col  = _SC.get(sc // 100, GREY)
    qs   = f"?{request.url.query}" if request.url.query else ""
    print(f"  {col}{sc}{RESET}  {GREY}{request.method:<7}{RESET} {path}{qs}")
    return resp

@asynccontextmanager
async def lifespan(app: FastAPI):
    sep = f"{GREY}  {'─' * 48}{RESET}"
    print(f"\n{BOLD}{CYAN}  🇨🇴  {settings.APP_NAME}{RESET}")
    print(sep)
    create_tables()
    print(f"{GREEN}  ✓  Base de datos lista{RESET}")
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()
    try:
        chunks = load_documents_to_rag()
        if chunks > 0:
            print(f"{GREEN}  ✓  RAG listo — {chunks} documentos activos{RESET}")
        else:
            print(f"{YELLOW}  ⚠  RAG vacío — agrega contenido en Panel → Base de Conocimiento{RESET}")
    except Exception as e:
        print(f"{YELLOW}  ⚠  RAG no cargó: {e}{RESET}")
    print(sep)
    print(f"  {CYAN}🌐  Backend{RESET}  →  http://localhost:8000")
    print(f"  {CYAN}📊  Panel{RESET}    →  http://localhost:3000")
    print(f"  {CYAN}📖  Docs{RESET}     →  http://localhost:8000/docs")
    print(f"{sep}\n")
    yield
    print(f"\n{GREY}  ─  Servidor detenido{RESET}\n")

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              docs_url="/docs" if settings.DEBUG else None)

app.middleware("http")(_log_req)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(webhook_router)
app.include_router(api_router)
app.include_router(broadcast_router)
app.include_router(auth_router)
app.include_router(knowledge_router)   # ← NUEVO

@app.get("/")
async def root(): return {"status": "online", "app": settings.APP_NAME}

@app.get("/health")
async def health(): return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,
                reload=True, log_level="critical", access_log=False)

## ─── AGREGAR ESTO AL FINAL DE main.py ────────────────────────────
## Justo antes del bloque:  if __name__ == "__main__":

import threading
import urllib.request

def _keep_alive():
    """Hace ping al propio servidor cada 9 minutos para evitar el sleep de Render."""
    import time
    # Espera 2 minutos al arrancar antes del primer ping
    time.sleep(120)
    while True:
        try:
            url = "https://abelardo-bot-backend.onrender.com/health"
            urllib.request.urlopen(url, timeout=10)
            log.info("Keep-alive ping OK")
        except Exception as e:
            log.warning(f"Keep-alive falló: {e}")
        time.sleep(540)   # 9 minutos

# Arranca el hilo en background al iniciar el servidor
_keep_alive_thread = threading.Thread(target=_keep_alive, daemon=True)
_keep_alive_thread.start()