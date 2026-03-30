# 📄 backend/services/rag.py  ← REEMPLAZA EL ANTERIOR
"""
RAG que lee de la BD (knowledge_docs) + scraping automático
de defensoresdelapatria.com al arrancar el servidor.
"""
import re
import logging
import httpx

log = logging.getLogger("abelardo_bot")


def _tokenize(text: str) -> set[str]:
    t = text.lower()
    for a, b in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ñ','n'),
                 ('à','a'),('è','e'),('ì','i'),('ò','o'),('ù','u')]:
        t = t.replace(a, b)
    words = re.findall(r'\b[a-z]{3,}\b', t)
    stopwords = {
        'que','con','los','las','del','una','por','para','son','sus',
        'nos','mas','pero','como','esta','este','esto','ser','hay',
        'fue','han','tiene','van','sea','muy','bien','cuando','donde',
        'porque','sobre','entre','todo','todos','cada','solo','sin',
        'the','and','for','are','was','this','that','with','from',
    }
    return set(w for w in words if w not in stopwords)


def _clean_html(html: str) -> str:
    """Elimina tags HTML y limpia el texto."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def scrape_website(url: str) -> str:
    """Descarga y extrae texto de una URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AbelardoBot/1.0)"}
        r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            return _clean_html(r.text)
        log.warning(f"Scraping {url}: status {r.status_code}")
        return ""
    except Exception as e:
        log.error(f"Scraping error {url}: {e}")
        return ""


def load_documents_to_rag() -> int:
    """
    Al arrancar:
    1. Verifica documentos en BD
    2. Hace scraping de defensoresdelapatria.com si no hay doc de esa fuente
    """
    try:
        from models.database import SessionLocal
        from models.knowledge import KnowledgeDoc
        from config import get_settings
        settings = get_settings()

        db = SessionLocal()

        # Verificar si ya existe el documento del sitio web
        existing = db.query(KnowledgeDoc).filter(
            KnowledgeDoc.source == "web_scrape"
        ).first()

        if not existing and settings.RAG_SCRAPE_URL:
            log.info(f"RAG: scraping {settings.RAG_SCRAPE_URL}...")
            content = scrape_website(settings.RAG_SCRAPE_URL)
            if content and len(content) > 100:
                doc = KnowledgeDoc(
                    title    = "Sitio web oficial Defensores de la Patria",
                    category = "general",
                    content  = content[:8000],  # máximo 8000 chars
                    source   = "web_scrape",
                    active   = True,
                )
                db.add(doc)
                db.commit()
                log.info("RAG: sitio web importado correctamente")

        count = db.query(KnowledgeDoc).filter(KnowledgeDoc.active == True).count()
        db.close()

        if count > 0:
            log.info(f"RAG: {count} documentos activos")
        else:
            log.warning("RAG: sin documentos — agrega contenido en Panel → Base de Conocimiento")
        return count

    except Exception as e:
        log.error(f"RAG init error: {e}")
        return 0


def refresh_web_scrape() -> bool:
    """Vuelve a hacer scraping del sitio web y actualiza el documento."""
    try:
        from models.database import SessionLocal
        from models.knowledge import KnowledgeDoc
        from config import get_settings
        settings = get_settings()

        content = scrape_website(settings.RAG_SCRAPE_URL)
        if not content or len(content) < 100:
            return False

        db = SessionLocal()
        existing = db.query(KnowledgeDoc).filter(
            KnowledgeDoc.source == "web_scrape"
        ).first()

        if existing:
            existing.content = content[:8000]
        else:
            db.add(KnowledgeDoc(
                title    = "Sitio web oficial Defensores de la Patria",
                category = "general",
                content  = content[:8000],
                source   = "web_scrape",
                active   = True,
            ))

        db.commit()
        db.close()
        log.info("RAG: sitio web actualizado")
        return True

    except Exception as e:
        log.error(f"RAG refresh error: {e}")
        return False


def query_rag(query: str, k: int = 4) -> str:
    """Busca documentos relevantes en la BD."""
    try:
        from models.database import SessionLocal
        from models.knowledge import KnowledgeDoc

        db = SessionLocal()
        docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.active == True).all()
        db.close()

        if not docs:
            return ""

        query_words = _tokenize(query)
        if not query_words:
            return ""

        scored = []
        for doc in docs:
            full_text = f"{doc.title} {doc.category} {doc.content}"
            doc_words = _tokenize(full_text)
            common    = query_words & doc_words
            if common:
                category_bonus = 0.3 if doc.category.lower() in query.lower() else 0
                score = len(common) / len(query_words) + category_bonus
                paragraphs = [p.strip() for p in re.split(r'\n{2,}', doc.content) if len(p.strip()) > 30]
                for para in paragraphs:
                    para_words  = _tokenize(para)
                    para_common = query_words & para_words
                    if para_common:
                        scored.append((score + len(para_common) * 0.1, para))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [text for _, text in scored[:k]]
        return "\n\n---\n\n".join(top)

    except Exception as e:
        log.error(f"RAG query error: {e}")
        return ""