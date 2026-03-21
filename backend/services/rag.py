# 📄 backend/services/rag.py  ← REEMPLAZA EL ANTERIOR
"""
RAG que lee de la base de datos (tabla knowledge_docs).
Se actualiza en tiempo real cuando agregas documentos desde el panel.
Sin chromadb, sin compilación — funciona en Python 3.14.
"""
import re
import logging

log = logging.getLogger("abelardo_bot")


def _tokenize(text: str) -> set[str]:
    """Normaliza y tokeniza texto en español."""
    t = text.lower()
    for a, b in [('á','a'),('à','a'),('é','e'),('è','e'),('í','i'),
                 ('ì','i'),('ó','o'),('ò','o'),('ú','u'),('ù','u'),('ñ','n')]:
        t = t.replace(a, b)
    words = re.findall(r'\b[a-z]{3,}\b', t)
    stopwords = {
        'que','con','los','las','del','una','por','para','son','sus',
        'nos','mas','pero','como','esta','este','esto','ser','hay',
        'fue','han','tiene','van','sea','muy','bien','cuando','donde',
        'porque','sobre','entre','todo','todos','cada','solo','sin',
    }
    return set(w for w in words if w not in stopwords)


def load_documents_to_rag() -> int:
    """
    Verifica que la tabla knowledge_docs exista.
    Los documentos se leen en tiempo real desde query_rag().
    """
    try:
        from models.database import SessionLocal
        from models.knowledge import KnowledgeDoc
        db = SessionLocal()
        count = db.query(KnowledgeDoc).filter(KnowledgeDoc.active == True).count()
        db.close()
        if count > 0:
            log.info(f"RAG: {count} documentos activos en la base de datos")
        else:
            log.warning("RAG: sin documentos — agrega contenido en Panel → Base de Conocimiento")
        return count
    except Exception as e:
        log.error(f"RAG init error: {e}")
        return 0


def query_rag(query: str, k: int = 4) -> str:
    """
    Busca los documentos más relevantes en la BD para la consulta.
    Lee directo de la tabla knowledge_docs — siempre actualizado.
    """
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
            full_text  = f"{doc.title} {doc.category} {doc.content}"
            doc_words  = _tokenize(full_text)
            common     = query_words & doc_words
            if common:
                # Bonus si la categoría coincide exactamente
                category_bonus = 0.3 if doc.category.lower() in query.lower() else 0
                score = len(common) / len(query_words) + category_bonus
                # Dividir contenido largo en párrafos para contexto más preciso
                paragraphs = [p.strip() for p in re.split(r'\n{2,}', doc.content) if len(p.strip()) > 30]
                for para in paragraphs:
                    para_words = _tokenize(para)
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