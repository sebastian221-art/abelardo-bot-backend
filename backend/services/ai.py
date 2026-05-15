# 📄 backend/services/ai.py  ← REEMPLAZA EL ANTERIOR
"""
Motor de IA del ChatBot Abelardo 2026.
- Detecta la intención del mensaje
- Consulta el RAG con documentos de Abelardo
- Genera la respuesta con tono de campaña
- Envía mensaje de testigos de mesa UNA SOLA VEZ por contacto
"""
import logging
from groq import Groq
from config import get_settings
from services.rag import query_rag

settings = get_settings()
log      = logging.getLogger("abelardo_bot")
client   = Groq(api_key=settings.GROQ_API_KEY)

MODEL = "llama-3.3-70b-versatile"

TESTIGOS_MSG = (
    "\n\n🇨🇴 ¡Llegó el momento de unirnos por la Defensa de la Patria!\n\n"
    "Te invitamos a inscribirte como *TESTIGO DE MESA*, protejamos nuestros votos 💪🏻🧐🐯\n\n"
    "Si eres mayor de edad, registra tus datos aquí:\n"
    "https://defensores.defensoresdelapatria.com/registro.php?departamento=27&nombre=SANTANDER&tipo=departamento\n\n"
    "Te estaremos contactando para que accedas a las capacitaciones.\n\n"
    "✅ Si ya llenaste el formulario, confírmalo escribiendo al 📱 *320 852 1491*"
)


def _ya_recibio_testigos(phone: str) -> bool:
    """Verifica si este contacto ya recibió el mensaje de testigos."""
    try:
        from models.database import SessionLocal
        from models.contact  import Contact
        db = SessionLocal()
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        db.close()
        if not contact:
            return False
        # Usamos el campo 'segment' como flag temporal
        # Si tiene 'testigos_enviado' en metadata o segment, ya lo recibió
        return bool(contact.segment and 'testigos' in str(contact.segment))
    except Exception as e:
        log.error(f"Error verificando testigos para {phone}: {e}")
        return False


def _marcar_testigos_enviado(phone: str):
    """Marca que este contacto ya recibió el mensaje de testigos."""
    try:
        from models.database import SessionLocal
        from models.contact  import Contact
        db = SessionLocal()
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        if contact:
            # Guardamos en segment que ya recibió el mensaje
            contact.segment = 'testigos_enviado'
            db.commit()
        db.close()
    except Exception as e:
        log.error(f"Error marcando testigos para {phone}: {e}")


# ── Intenciones que el bot puede detectar ────────────────────────
INTENTS = {
    "optin":       ["quiero recibir", "suscribir", "inscribir", "sí quiero", "acepto", "unirme"],
    "optout":      ["no quiero", "cancelar", "dejarme de enviar", "salir", "baja", "stop"],
    "propuesta":   ["propuesta", "plan", "qué va a hacer", "programa", "gobierno"],
    "seguridad":   ["seguridad", "violencia", "crimen", "policía", "matar", "robo", "inseguro"],
    "economia":    ["empleo", "trabajo", "economía", "desempleo", "empresa", "pymes", "sueldo"],
    "salud":       ["salud", "hospital", "médico", "eps", "medicina", "enfermedad"],
    "educacion":   ["educación", "colegio", "universidad", "estudio", "becas", "maestros"],
    "paz":         ["paz", "guerrilla", "farc", "negociación", "conflicto", "armado"],
    "corrupcion":  ["corrupción", "robo", "ladrones", "político", "transparencia"],
    "encuesta":    ["encuesta", "pregunta", "opinar", "votar", "calificación"],
    "embajador":   ["invitar", "compartir", "amigos", "referir", "embajador", "link"],
    "debate":      ["debate", "entrevista", "programa", "canal", "cuando habla"],
    "saludo":      ["hola", "buenos", "buenas", "hey", "qué tal", "cómo están"],
}


def detect_intent(text: str) -> str:
    """Detecta la intención del mensaje del usuario."""
    lower = text.lower()
    for intent, keywords in INTENTS.items():
        if any(kw in lower for kw in keywords):
            return intent
    return "consulta_general"


SYSTEM_PROMPT = """Eres el asistente oficial de la campaña presidencial de Abelardo de la Espriella para Colombia 2026.

Tu misión:
- Responder preguntas sobre las propuestas, posiciones y plan de gobierno de Abelardo
- Hablar con calidez, respeto y entusiasmo por Colombia
- Ser claro, directo y honesto
- Generar cercanía con el ciudadano

Reglas estrictas:
- SOLO responde con información documentada y verificada de Abelardo
- Si no tienes la información exacta, dilo con honestidad y ofrece contacto oficial
- NO inventes propuestas ni estadísticas
- NO ataques a otros candidatos — habla de propuestas, no de personas
- NO hagas promesas que no estén en el programa oficial
- Responde SIEMPRE en español colombiano, sin tecnicismos
- Máximo 3 párrafos cortos — WhatsApp no es para textos largos
- Usa emojis con moderación (1-2 por mensaje máximo)

Cuando el usuario mencione temas de seguridad, economía, salud, educación o paz,
usa el contexto del programa de gobierno para dar respuestas concretas."""


async def process_message(
    phone:        str,
    message:      str,
    history:      list[dict],
    contact_name: str = "",
) -> tuple[str, str]:
    """
    Procesa el mensaje del usuario y retorna (respuesta, intención).
    history: lista de {"role": "user"|"assistant", "content": "..."}
    """

    intent  = detect_intent(message)
    context = query_rag(message)

    # Mensajes especiales sin IA
    if intent == "optin":
        reply = (
            f"¡Bienvenido{',' + ' ' + contact_name if contact_name else ''} al movimiento! 🇨🇴\n\n"
            "Gracias por unirte. Te mantendré informado con las últimas noticias "
            "de la campaña de Abelardo de la Espriella.\n\n"
            "Puedes preguntarme sobre sus propuestas, debates o eventos en tu ciudad. "
            "Y si quieres dejar de recibir mensajes, solo escribe *STOP*."
        )
        if not _ya_recibio_testigos(phone):
            reply += TESTIGOS_MSG
            _marcar_testigos_enviado(phone)
        return reply, intent

    if intent == "optout":
        return (
            "Entendido. Has salido de la lista de mensajes de la campaña.\n\n"
            "Si en algún momento quieres volver, solo escríbenos. ¡Gracias por tu tiempo! 🙏",
            intent,
        )

    if intent == "embajador":
        reply = (
            f"¡Gracias por querer sumarte como embajador! 🌟\n\n"
            "Pronto activaremos el sistema de referidos para que puedas invitar "
            "a tus amigos y familia. Te avisamos cuando esté listo.\n\n"
            "Mientras tanto, comparte nuestros mensajes con quien creas que "
            "le puede interesar el futuro de Colombia. 🇨🇴"
        )
        if not _ya_recibio_testigos(phone):
            reply += TESTIGOS_MSG
            _marcar_testigos_enviado(phone)
        return reply, intent

    # ── Respuesta con IA + RAG ────────────────────────────────────
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\nINFORMACIÓN RELEVANTE DEL PROGRAMA DE ABELARDO:\n{context}"

    if contact_name:
        system += f"\n\nEl ciudadano se llama {contact_name}. Puedes llamarle por su nombre."

    messages = [{"role": "system", "content": system}]

    # Agregar historial reciente (últimas 6 interacciones)
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.6,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Error Groq: {e}")
        reply = (
            "En este momento tengo un problema técnico. 😔\n"
            "Por favor intenta de nuevo en unos minutos o escríbenos a "
            "nuestro canal oficial."
        )

    # Agregar mensaje de testigos UNA SOLA VEZ por contacto
    if not _ya_recibio_testigos(phone):
        reply += TESTIGOS_MSG
        _marcar_testigos_enviado(phone)

    return reply, intent