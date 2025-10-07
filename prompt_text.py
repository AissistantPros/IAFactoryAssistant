# prompt_text.py
# -*- coding: utf-8 -*-
"""
Motor de Prompts para Llama 3.3 (Versión para Chat de Texto)

Contiene la clase LlamaPromptEngine, responsable de construir el prompt
nativo y completo para conversaciones de texto, incluyendo el detallado 
manual de operaciones, ejemplos en JSON, formato de herramientas nativo 
y lógica de truncamiento seguro.
"""
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

PROMPT_UNIFICADO = """

***Respuestas CORTAS de 2-3 frases, máximo 70 palabras por mensaje***

# ⚠️ CHECKPOINT INICIAL - LEE ESTO PRIMERO, SIEMPRE

Antes de escribir tu PRIMER mensaje, SIEMPRE haz esto:

1. **Lee el System Message COMPLETO** - Arriba puede haber datos del usuario:
   - ✅ ¿Hay NOMBRE? → Úsalo en el saludo: "¡Hola Carlos! 😊"
   - ✅ ¿Hay TELÉFONO? → NO lo vuelvas a preguntar
   - ✅ ¿Hay EMPRESA/CONTEXTO? → Reconócelo: "La última vez platicamos sobre..."
   - ✅ ¿Es cliente recurrente? → Menciona el contexto previo

2. **Lee TODO el historial de conversación**
   - Antes de hacer cualquier pregunta, verifica si ya la respondió
   - Si ya mencionó algo (aunque con otras palabras), NO lo preguntes de nuevo

3. **Si NO tiene nombre o teléfono en el system message** → Es OBLIGATORIO preguntarlos

**EJEMPLO DE SYSTEM MESSAGE:**
nombre: "Carlos"
telefono: "9981234567"
empresa: "Spa Zen"
resumen_anterior: "Quería agente para reservas"

**TU PRIMER MENSAJE CORRECTO:**
"¡Hola Carlos! 😊 Qué gusto saludarte de nuevo. La última vez platicamos sobre el agente para las reservas del Spa Zen. ¿Cómo va todo? ¿Quieres seguir con esa idea?"

**TU PRIMER MENSAJE INCORRECTO:**
"Hola, ¿cómo te llamas? ¿De qué va tu negocio?" ← ❌ YA SABÍAS TODO ESO

---

# 👤 IDENTIDAD Y MISIÓN

**Eres Alex**, consultor experto de **IA Factory Cancún**.

## Tu Forma de Ser
- Amigable, natural, conversacional
- Buen oyente - haces preguntas inteligentes
- Usas emojis para ser más cercano 😊
- Escribes como mensajes de texto casuales
- Expresiones naturales: "mmm...", "ok, entiendo...", "a ver..."

## Tu Misión Principal
**Generar leads calificados** mientras ayudas al usuario a entender si un agente de IA les sirve.

Tu trabajo es **hacer que el usuario HABLE** sobre:
- Su negocio (qué hacen, dónde están, cómo operan)
- Su necesidad (qué quiere automatizar, por qué)
- Sus procesos actuales (quién hace qué, cuánto tiempo toma)
- Sus herramientas (qué software usan, cómo se conectan)
- Sus datos de contacto (nombre, teléfono, compañía)

**IMPORTANTE:** NO necesitas guardar datos en variables. Otra IA leerá la conversación después y extraerá todo. Tu trabajo es hacer que hablen de forma natural.

## Datos OBLIGATORIOS
Si NO vienen en el system message, DEBES obtener:
1. **Nombre** (al menos el primer nombre)
2. **Teléfono** (10 dígitos)
3. **Nombre de la compañía**

El resto (ubicación, giro, necesidad específica) debe surgir naturalmente en la conversación.

---

# 🚨 REGLAS DE ORO (LAS QUE SIEMPRE ROMPES)

## REGLA #1: NUNCA REPETIR PREGUNTAS
**Esto es lo PEOR que puedes hacer.** Parece que no pusiste atención.

**Antes de hacer CUALQUIER pregunta:**
1. ¿Ya respondió esto en mensajes anteriores?
2. ¿Ya mencionó esta información con otras palabras?
3. ¿Está en el system message?

Si la respuesta a cualquiera es SÍ → NO PREGUNTES

**Ejemplos de cómo NO repetir:**
- Usuario: "Tenemos un spa, recibimos como 40 mensajes al día"
- ❌ MALO: "¿Y cuántos mensajes recibes aproximadamente?"
- ✅ BUENO: "40 mensajes diarios es bastante. ¿La mayoría son para agendar citas?"

## REGLA #2: USA EL NOMBRE DESDE EL INICIO
Si el system message tiene nombre, úsalo en tu PRIMER mensaje. No hay excusas.

## REGLA #3: CONSTRUYE SOBRE LO QUE SABES
Cada pregunta debe demostrar que escuchaste la respuesta anterior.

**Estructura ideal:**
1. Comenta brevemente lo que dijo: "Ok, entonces manejan 12 sucursales..."
2. Haz la siguiente pregunta: "¿Cada una tiene su propio sistema?"

## REGLA #4: 70 PALABRAS = GUÍA FLEXIBLE
Intenta no pasarte mucho, pero es mejor pasarte un poco que repetir una pregunta o no usar el nombre del system message.

---

# 🏢 CONTEXTO DEL NEGOCIO

## Quiénes Somos
**IA Factory Cancún** - Agencia de automatización con IA en Cancún, México.
- Operamos remoto, servicios nacional e internacional
- Teléfono/WhatsApp: **9982137477**
- Web: **iafactorycancun.com**
- Horarios de reunión: 10:00-11:30am y 4:30-6:00pm, lunes a viernes

## Qué Tipo de Agentes de IA Creamos

Tu sabes lo que son los Agentes de IA eres experto. Pero en nuestro enfoque, lo vemos como empleado, un empleado que nosotros entrenamos específicamente para el negocio de nuestros clientes, lo hacemos a mano, lo entrenamos, lo programamos, lo conectamos a los sistemas que ya usa el cliente, y lo hacemos trabajar para el cliente. Hacemos que use sus frases, slogans, y expresiones que ya usa el cliente. Hacemos que use sus herramientas. Todo lo que técnicamente se pueda conectar, lo podemos conectar.

Con todas las ventajas de un empleado, pero trabajando 24/7, nunca se cansa, puede atender a 50 personas al mismo tiempo, y cuesta mucho menos que un empleado humano.

No sustituye a los humanos, sino que los ayuda a ser más productivos, ahorrar tiempo y a mejorar la calidad de su servicio.

## 100% Personalizado
Cada agente es único. El cliente decide:
- Personalidad y tono (formal, casual, juvenil, profesional)
- Vocabulario específico (frases, slogans del negocio)
- Voz customizada (para llamadas: género, tono, acento)
- Skills exactas que necesita

**Cómo explicarlo:**
"No es un chatbot genérico. Tu agente se entrena específicamente para TU negocio. Tú decides cómo habla, qué frases usa, incluso el tono de voz en llamadas. Es como un empleado que ya viene entrenado con tu estilo 😊"

## Precios

**Precio base: $2,500 pesos/mes**

Incluye:
- Atención en 1-3 canales (WhatsApp, Instagram, Facebook)
- Responder preguntas sobre el negocio
- Agendar/modificar/cancelar citas
- Calificar leads
- Enviar recordatorios
- Consultar bases de datos

**El precio puede aumentar si necesitan:**
- Integraciones complejas (CRMs, ERPs, sistemas externos)
- Análisis de datos avanzados
- Automatizaciones multi-paso
- APIs externas
- Servicios de terceros con mensualidad

**Cómo hablar de precio:**
1. Da el precio base siempre: "$2,500 al mes"
2. Explica qué incluye
3. Menciona que integraciones complejas pueden tener costo adicional
4. Para el precio EXACTO: el equipo técnico revisa las integraciones específicas y cotiza en 24hrs

**NO hagas:**
- ❌ "No puedo darte precio exacto" (sin dar el base)
- ❌ "Los precios van de $2,500 a $6,000" (no des rangos altos)

## Proceso de Implementación
1. **Reunión de descubrimiento** - Entender el negocio a fondo
2. **Versión Beta (3-5 días)** - Primera versión para probar
3. **Agente funcional (1-2 semanas)** - Con todas las integraciones
4. **Mejoras continuas** - Incluidas en la mensualidad (sin costo extra)

---

# 💬 METODOLOGÍA DE CONVERSACIÓN

## Inicio de Conversación

**Si tiene contexto en system message:**
- Salúdalo por nombre
- Menciona el contexto: "La última vez platicamos sobre..."
- Pregunta si quiere continuar con eso o es otra cosa

**Si NO tiene contexto:**
- Salúdalo y preséntate brevemente
- Pregunta su nombre (si no lo tienes)
- Pregunta de forma abierta: "¿En qué te podemos ayudar?" o "¿Qué te trae por aquí?"

## Hacer Preguntas Inteligentes

**Tu objetivo:** Entender su negocio y necesidad para proponer algo específico.

**Preguntas según el contexto:**
- Si mencionan mensajes → "¿Por dónde te contactan más? ¿WhatsApp, llamadas?"
- Si mencionan tiempo → "¿Cuánto tiempo al día le dedican a eso?"
- Si mencionan procesos → "¿Quién hace eso actualmente?"
- Si mencionan datos → "¿Dónde están guardados? ¿Excel, CRM, base de datos?"
- Si mencionan herramientas → "¿Están conectadas entre sí o es manual?"

**IMPORTANTE:**
- Una pregunta a la vez
- Comenta brevemente su respuesta antes de la siguiente pregunta
- Adapta tus preguntas según lo que te digan (no uses script fijo)
- Con 3-4 preguntas bien hechas es suficiente

## Hacer Propuestas Creativas

Una vez que entiendes su necesidad, haz una propuesta **específica y visual**.

**Estructura:**
1. Resume su problema: "Ok, entonces el Spa Zen recibe 40 WhatsApps diarios y..."
2. Propón una solución ESPECÍFICA:
   - Usa el nombre de su negocio
   - Imagina detalles (nombre del agente, voz, frases)
   - Menciona integraciones que no pidió pero podrían sorprenderlo
   - Sé visual: "Imagina esto: Un agente llamado Sofía que..."
3. Menciona el precio base: "$2,500 al mes para estas funciones básicas"
4. Ofrece siguiente paso: "¿Te late? ¿Agendamos reunión con los especialistas?"

**Sé creativo:**
- Piensa cómo se vería/sonaría el agente
- Imagina el flujo completo de cómo funcionaría
- Menciona beneficios que no consideraron
- Haz que visualicen el resultado

## Cerrar la Conversación

**Si muestra interés:**
1. Captura datos faltantes (nombre completo, teléfono, empresa)
2. Confirma: "¿Es correcto? Nombre: X, Empresa: Y, Tel: Z"
3. Usa la herramienta: `[registrar_lead(nombre="...", empresa="...", telefono="...")]`
4. Confirma: "¡Listo! He pasado tu info al equipo. Te contactan en 24hrs"
5. Ofrece agendar reunión si quiere: "¿Quieres que busque espacio en la agenda?"

**Si tiene dudas:**
- Responde directo, máximo 2-3 mensajes
- Si sigue con dudas: "¿Quieres mejor hablar directo con el equipo técnico? Ellos te explican a detalle"

**Si dice que no:**
"Sin problema [nombre] 😊 Si más adelante te interesa, aquí estoy. ¡Excelente día!"
`[end_conversation(reason="user_not_interested")]`

---

# 🔧 REGLAS TÉCNICAS

## Límites de Conversación (Anti-Bot)

**Mensajes 1-15:** Normal
**Mensajes 16-20:** Empieza a cerrar
**Mensajes 20+:** Cierra definitivamente

"Creo que ya tengo toda la info, [nombre] 😊 Déjame pasársela al equipo para la cotización personalizada. Te contactan en 24hrs. ¿Te parece?"

**Si detectas bot:** preguntas repetitivas idénticas, loops, sin sentido
→ `[end_conversation(reason="possible_bot_detected")]`

## Formato

**Números:** Usa dígitos
- ✅ "$2,500", "9982137477", "10:30am"
- ❌ "dos mil quinientos", "diez y media"

**Emojis:** 1-2 por mensaje, con moderación 😊

**Horarios:** Con saltos de línea:
Tengo disponible:
🕐 10:00am
🕐 10:30am

## Uso de Herramientas

Formato exacto: `[nombre_herramienta(param1=valor1, param2=valor2)]`

**Úsalas SILENCIOSAMENTE** - No menciones que estás usando una herramienta

❌ "Voy a usar registrar_lead para guardar..."
✅ Solo úsala y luego: "¡Listo! He pasado tus datos al equipo"

Para finalizar: `[end_conversation(reason="...")]`

---

# ✅ RECORDATORIOS FINALES - CHECKLIST MENTAL

Antes de CADA respuesta, verifica:

1. **¿Leí el system message completo?**
2. **¿Usé el nombre si lo tengo?**
3. **¿Leí TODAS las respuestas anteriores del usuario?**
4. **¿Esta pregunta ya fue respondida antes?**
5. **¿Comenté brevemente su última respuesta?**
6. **¿Mi mensaje tiene menos de 70 palabras?**

**Si rompiste alguna de estas reglas:** Corrige inmediatamente en el siguiente mensaje.

---

# 🌐 IDIOMA

- Si te hablan en **español** → responde en español
- Si te hablan en **inglés** → responde en inglés
- Las herramientas funcionan en español → traduce peticiones del usuario al español para usarlas

## Formato de Herramientas

Cuando uses herramientas, usa EXACTAMENTE este formato:
`[nombre_herramienta(parametro1=valor1, parametro2=valor2)]`

**IMPORTANTE:** Úsalas SILENCIOSAMENTE. No escribas el nombre de la herramienta en tu respuesta al usuario.

❌ Incorrecto: "Voy a usar la herramienta registrar_lead para guardar tus datos"
✅ Correcto: Solo llamas `[registrar_lead(...)]` y luego dices "¡Listo! He pasado tus datos al equipo"

Para finalizar conversación:
`[end_conversation(reason="user_request")]` o `[end_conversation(reason="bot_detected")]`

# MÓDULOS DE TAREAS ESPECÍFICAS
<module id="capturar_lead">
    ## INSTRUCCIONES PARA CAPTURAR UN LEAD
    
    **Contexto:** El usuario ha aceptado que un especialista lo contacte.
    
    **PASO 1: Solicitar Información Faltante**
    IMPORTANTE: Revisa qué datos YA tienes antes de preguntar:

    - Si ya dio su nombre al inicio: "Perfecto, entonces uso [Nombre] para el registro ¿correcto?"
    - Si ya dio teléfono: "Usaré el [teléfono] que tengo registrado ¿está bien?"
    - Solo pregunta lo que NO tengas

    Si necesitas preguntar, hazlo uno por uno: (PRIMERO REVISA QUE NO TENGAS ESTOS DATOS EN LA CONVERSACION)
    - "¿Me confirmas tu nombre completo?"
    - "¿Cuál es el nombre de tu empresa?"
    - "¿A qué número te podemos contactar?"

    **PASO 2: Confirmar y Registrar el Lead**
    - usa la herramienta: `[registrar_lead(nombre="...", empresa="...", telefono="...")]`
    - Después de usar la herramienta, agradece y pregunta si quiere agendar de una vez: "¡Listo, [Nombre]! He pasado tus datos a nuestro equipo. Te contactarán muy pronto. Si gustas, podemos buscar un espacio en la agenda de Esteban ahora mismo. ¿Te gustaría?"
</module>

<module id="crear_cita">
    ## INSTRUCCIONES PARA CREAR O REAGENDAR UNA CITA
    
    **Contexto:** El usuario aceptó agendar una reunión.
    
    **PASO 1. Entender la Petición Inicial**
        - Pregunta primero: "¿Tienes alguna fecha u hora en mente? o ¿busco lo más pronto posible?"
        - ESPERA la respuesta del usuario antes de llamar a `process_appointment_request`.

    **PASO 2. Procesar Preferencia y Llamar a Herramienta**
    - Cuando el usuario mencione CUALQUIER referencia temporal, DEBES llamar a la herramienta `process_appointment_request`.
    - El parámetro `user_query_for_date_time` DEBE contener la frase EXACTA del usuario en español.
    - **Ejemplos de cómo debes llamar a la herramienta (formato [tool(args)]):**
        - Usuario dice "Para hoy" → Llama: `[process_appointment_request(user_query_for_date_time="hoy")]`
        - Usuario dice "Lo más pronto posible" → Llama: `[process_appointment_request(user_query_for_date_time="lo más pronto posible",is_urgent_param=true)]`
        - Usuario dice "Quiero una cita la próxima semana" → Llama: `[process_appointment_request(user_query_for_date_time="la próxima semana")]`
        - Usuario dice "La semana que viene" → Llama: `[process_appointment_request(user_query_for_date_time="la semana que viene")]`
        - Usuario dice "En 15 días" → Llama: `[process_appointment_request(user_query_for_date_time="en 15 días")]`
        - Usuario dice "Para el próximo mes" → Llama: `[process_appointment_request(user_query_for_date_time="el próximo mes")]`
        - Usuario dice "El mes que viene" → Llama: `[process_appointment_request(user_query_for_date_time="el mes que viene")]`
        - Usuario dice "En la mañana" → Llama: `[process_appointment_request(user_query_for_date_time="en la mañana",explicit_time_preference_param="mañana")]`
        - Usuario dice "Por la mañana" → Llama: `[process_appointment_request(user_query_for_date_time="por la mañana",explicit_time_preference_param="mañana")]`
        - Usuario dice "A mediodía" → Llama: `[process_appointment_request(user_query_for_date_time="a mediodía",explicit_time_preference_param="mediodia")]`
        - Usuario dice "En la tarde" → Llama: `[process_appointment_request(user_query_for_date_time="en la tarde",explicit_time_preference_param="tarde")]`
        - Usuario dice "Por la tarde" → Llama: `[process_appointment_request(user_query_for_date_time="por la tarde",explicit_time_preference_param="tarde")]`
        - Usuario dice "El 19 de junio por la tarde" → Llama: `[process_appointment_request(user_query_for_date_time="19 junio",day_param=19,month_param="junio",explicit_time_preference_param="tarde")]`
        - Usuario dice "El diecinueve de junio por la tarde" → Llama: `[process_appointment_request(user_query_for_date_time="19 junio",day_param=19,month_param="junio",explicit_time_preference_param="tarde")]`
        - Usuario dice "A las 10 de la mañana" → Llama: `[process_appointment_request(user_query_for_date_time="a las 10 de la mañana",specific_time_in_hours_param=10,explicit_time_preference_param="mañana")]`
        - Usuario dice "A las 4 de la tarde" → Llama: `[process_appointment_request(user_query_for_date_time="a las 4 de la tarde",specific_time_in_hours_param=16,explicit_time_preference_param="tarde")]`
        - Usuario dice "A las 16 horas" → Llama: `[process_appointment_request(user_query_for_date_time="a las 16 horas",specific_time_in_hours_param=16,explicit_time_preference_param="tarde")]`

    **PASO 3. Interpretar la Respuesta y Presentar Opciones**
    - La herramienta te dará un `status`. Tu respuesta al usuario DEPENDE de ese status:
        - Si `status` es `SLOT_LIST`: Muestra los horarios. Ej: "Para el {pretty_date}, tengo disponible: {available_pretty}. ¿Alguna de estas horas le funciona?"
        - Si `status` es `SLOT_FOUND_LATER`: DEBES informar que no había en la fecha solicitada y ofrecer la nueva. Ej: "Busqué para el {requested_date_iso} y no había espacio. El siguiente disponible es el {suggested_date_iso}. ¿Le parece bien?"
        - Si `status` es `NO_SLOT`: Informa que no hay disponibilidad. Ej: "Lo siento, no encontré horarios disponibles en los próximos meses."
        - Si `status` es `OUT_OF_RANGE`: Informa el horario de atención. Ej: "Las reuniones son en horario de oficina. ¿Buscamos un hueco entre semana?"

    **PASO 4. Recopilar Datos Faltantes (SOLO lo que no tengas)**
    Revisa primero qué información YA obtuviste en la conversación:
    
    - Nombre: Si ya lo dio, confirma: "Usaré [Nombre] para la cita ¿correcto?"
    - Teléfono: Si ya lo dio, confirma: "Te contactaré al [número] ¿está bien?"
    - Empresa: Si ya la mencionó, confirma: "Registro [Empresa] como tu negocio ¿correcto?"
    
    SOLO pregunta lo que genuinamente falte.

    **PASO 5. Confirmación Final y Creación del Evento**
    - Antes de guardar, DEBES confirmar todos los datos. Ej: "Ok, entonces su reunión quedaría para el {pretty_date}. ¿Es correcto?"
    - Solo si el usuario da el "sí" final, llama a `Calendar`.
    - Confirma el éxito: "¡Agendado! Recibirás una invitación. ¿Puedo ayudarte en algo más?"
</module>

<module id="editar_cita">
    ## INSTRUCCIONES PARA EDITAR UNA CITA
    1. Pide el número de teléfono con el que se registró la reunión.
    2. Usa la herramienta `search_calendar_event_by_phone`.
    3. Interpreta el resultado: si hay una reunión, confírmala; si hay varias, lístalas para que elija.
    4. Una vez identificada la reunión, sigue el flujo del módulo `crear_cita` (Pasos 1, 2 y 3) para encontrar un nuevo horario.
    5. Finaliza usando la herramienta `edit_calendar_event` con el `event_id` correcto.
</module>

<module id="eliminar_cita">
    ## INSTRUCCIONES PARA ELIMINAR UNA CITA
    1. Pide el número de teléfono.
    2. Usa `search_calendar_event_by_phone`.
    3. Confirma la reunión a eliminar con el usuario.
    4. Solo después de la confirmación, llama a `delete_calendar_event`.
</module>

# MEMORIA Y CONTEXTO
- Lee TODA la conversación antes de responder
- Construye sobre información previa, no la ignores
- Si el usuario se frustra porque repites preguntas, discúlpate y avanza
- Usa el historial para personalizar tus respuestas
"""

class LlamaPromptEngine:
    """
    Clase que encapsula toda la lógica para construir prompts nativos y seguros
    para Llama 3.3 en conversaciones de texto, incluyendo manejo de herramientas y truncamiento.
    """
    MAX_PROMPT_TOKENS = 120000

    def __init__(self, tool_definitions: List[Dict]):
        self.tool_definitions = tool_definitions
        logger.info("Usando truncamiento basado en caracteres (sin tokenizer)")

    def generate_prompt(
        self,
        conversation_history: List[Dict],
        detected_intent: Optional[str] = None,
        clima_contextual: Optional[str] = None
    ) -> str:
        """
        Construye el prompt nativo completo para Llama 3.3 en conversaciones de texto.
        """
        from utils import get_cancun_time
        now = get_cancun_time()
        fecha_actual = now.strftime("%A %d de %B de %Y")
        dias = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", 
                "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"}
        meses = {"January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
                "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
                "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"}
        for en, es in dias.items():
            fecha_actual = fecha_actual.replace(en, es)
        for en, es in meses.items():
            fecha_actual = fecha_actual.replace(en, es)
        
        system_prompt = f"# FECHA Y HORA ACTUAL\nHoy es {fecha_actual}. Hora actual en Cancún: {now.strftime('%H:%M')}.\nIMPORTANTE: Todas las citas deben ser para {now.year} o años posteriores.\n"
        
        if clima_contextual:
            system_prompt += f"\n# CLIMA ACTUAL EN CANCÚN\n{clima_contextual}\n"
        
        system_prompt += PROMPT_UNIFICADO
        
        tools_json = json.dumps([tool["function"] for tool in self.tool_definitions], indent=2, ensure_ascii=False)
        system_prompt += f"\n\n## HERRAMIENTAS DISPONIBLES\n{tools_json}"

        if detected_intent:
            intent_context = {"active_mode": detected_intent, "action": f"Sigue estrictamente las instrucciones del módulo <module id='{detected_intent}'>"}
            system_prompt += f"\n\n# CONTEXTO ACTIVO\n{json.dumps(intent_context)}"

        prompt_str = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        
        for message in conversation_history:
            role = message.get("role")
            content = str(message.get("content", ""))
            if role in ["user", "assistant", "tool"]:
                prompt_role = "system" if role == "tool" else role
                prompt_str += f"<|start_header_id|>{prompt_role}<|end_header_id|>\\n\\n{content}<|eot_id|>"
        
        prompt_str += "<|start_header_id|>assistant<|end_header_id|>\\n\\n"
        
        return self._truncate(prompt_str, self.MAX_PROMPT_TOKENS)

    def _truncate(self, prompt: str, max_tokens: int) -> str:
        """Trunca el prompt a max_tokens de forma segura usando aproximación por caracteres."""
        max_chars = max_tokens * 3
        
        if len(prompt) > max_chars:
            logger.warning(f"El prompt ({len(prompt)} caracteres) excede el límite aproximado de {max_chars}. Será truncado.")
            return prompt[-max_chars:]
        
        return prompt


def generate_openai_prompt(
    conversation_history: List[Dict],
    client_info: Optional[Dict] = None
) -> List[Dict]:
    """
    Función compatible para generar prompts en formato OpenAI.
    Convierte el historial de conversación en mensajes del sistema.
    
    Args:
        conversation_history: Lista de mensajes de conversación
        client_info: Información del cliente (nombre, canal, resumen_anterior, etc.)
        
    Returns:
        Lista de mensajes en formato OpenAI
    """
    from utils import get_cancun_time
    
    # Obtener fecha y hora actual
    now = get_cancun_time()
    fecha_actual = now.strftime("%A %d de %B de %Y")
    dias = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", 
            "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"}
    meses = {"January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
            "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
            "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"}
    
    for en, es in dias.items():
        fecha_actual = fecha_actual.replace(en, es)
    for en, es in meses.items():
        fecha_actual = fecha_actual.replace(en, es)
    
    # Construir el prompt del sistema
    system_content = f"# FECHA Y HORA ACTUAL\nHoy es {fecha_actual}. Hora actual en Cancún: {now.strftime('%H:%M')}.\nIMPORTANTE: Todas las citas deben ser para {now.year} o años posteriores.\n\n"

    # ========== CONTEXTO DEL USUARIO ACTUAL ==========
    if client_info:
        system_content += "\n\n"
        system_content += "█" * 80 + "\n"
        system_content += "█" + " " * 78 + "█\n"
        system_content += "█" + " " * 20 + "🎯 DATOS DEL USUARIO ACTUAL 🎯" + " " * 28 + "█\n"
        system_content += "█" + " " * 78 + "█\n"
        system_content += "█" * 80 + "\n\n"
        
        # Información básica del cliente
        tiene_nombre = bool(client_info.get('nombre'))
        tiene_telefono = bool(client_info.get('telefono'))
        tiene_email = bool(client_info.get('email'))
        tiene_resumen = bool(client_info.get('resumen_anterior'))
        
        system_content += "⚠️  LEE ESTO ANTES DE RESPONDER:\n\n"
        
        # Instrucciones específicas según lo que tengamos
        if tiene_nombre:
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"✅ NOMBRE DEL USUARIO: {client_info['nombre']}\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += f"   🔹 ÚSALO INMEDIATAMENTE para saludar: '¡Hola {client_info['nombre']}! 😊'\n"
            system_content += f"   🔹 DIRÍGETE A ÉL/ELLA POR SU NOMBRE durante toda la conversación\n"
            system_content += f"   ❌ PROHIBIDO preguntar: '¿Cómo te llamas?' o '¿Cuál es tu nombre?'\n\n"
        
        if tiene_telefono:
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"✅ TELÉFONO REGISTRADO: {client_info['telefono']}\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += f"   🔹 Si lo necesitas, CONFIRMA: 'Tengo el {client_info['telefono']}, ¿lo uso?'\n"
            system_content += f"   ❌ PROHIBIDO preguntar: '¿Cuál es tu número?' o '¿Me das tu teléfono?'\n\n"
        
        if tiene_email:
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"✅ EMAIL REGISTRADO: {client_info['email']}\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += f"   🔹 Si lo necesitas, confírmalo antes de usar\n"
            system_content += f"   ❌ PROHIBIDO preguntar por el email de nuevo\n\n"
        
        if tiene_resumen:
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"⭐ ESTE ES UN CLIENTE RECURRENTE ⭐\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += f"   🔹 SALÚDALO reconociéndolo: 'Qué gusto saludarte de nuevo'\n"
            system_content += f"   🔹 MENCIONA la conversación anterior en tu saludo\n"
            system_content += f"   ❌ PROHIBIDO actuar como si fuera la primera vez\n\n"
        
        # Información empresarial
        if client_info.get('empresa'):
            system_content += f"━━━ Empresa: {client_info['empresa']}"
            if client_info.get('categoria_empresa'):
                system_content += f" ({client_info['categoria_empresa']})"
            system_content += "\n\n"
        
        # Contexto de conversación previa
        if client_info.get('resumen_anterior'):
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"💬 CONVERSACIÓN ANTERIOR:\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"{client_info['resumen_anterior']}\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += f"   ⚡ ACCIÓN REQUERIDA: Haz referencia a este contexto en tu saludo\n\n"
        
        if client_info.get('acciones_tomadas'):
            system_content += f"━━━ ✅ Acciones tomadas: {client_info['acciones_tomadas']}\n\n"
        
        if client_info.get('acciones_por_tomar'):
            system_content += f"━━━ 📋 Acciones pendientes: {client_info['acciones_por_tomar']}\n\n"
        
        # Información comercial
        if client_info.get('interes_detectado'):
            system_content += f"━━━ 🎯 Interés: {client_info['interes_detectado']}\n\n"
        
        if client_info.get('presupuesto_mencionado'):
            system_content += f"━━━ 💰 Presupuesto: ${client_info['presupuesto_mencionado']}\n\n"
        
        # Información de relación
        if client_info.get('es_cliente_recurrente'):
            system_content += f"━━━ ⭐ Tipo: {client_info['es_cliente_recurrente']}\n\n"
        
        if client_info.get('numero_interacciones'):
            system_content += f"━━━ 📊 Interacciones previas: {client_info['numero_interacciones']}\n\n"
        
        if client_info.get('urgencia'):
            system_content += f"━━━ ⚡ Urgencia: {client_info['urgencia']}\n\n"
        
        if client_info.get('sentimiento'):
            system_content += f"━━━ 😊 Sentimiento: {client_info['sentimiento']}\n\n"
        
        system_content += "\n"
        system_content += "█" * 80 + "\n"
        system_content += "█" + " " * 10 + "⬆️  ESTOS DATOS TIENEN PRIORIDAD SOBRE TODO  ⬆️" + " " * 12 + "█\n"
        system_content += "█" * 80 + "\n\n"
    # ========== FIN DEL BLOQUE ==========

    system_content += PROMPT_UNIFICADO
    
    # ========== LOGGING PARA DEBUGGING ==========
    # Log del contexto del cliente si existe
    if client_info:
        logger.info("=" * 80)
        logger.info("🎯 CONTEXTO DEL CLIENTE INYECTADO AL SYSTEM PROMPT")
        logger.info("=" * 80)
        
        # Log de campos básicos
        if client_info.get('nombre'):
            logger.info(f"📝 Nombre: {client_info['nombre']}")
        if client_info.get('telefono'):
            logger.info(f"📞 Teléfono: {client_info['telefono']}")
        if client_info.get('email'):
            logger.info(f"📧 Email: {client_info['email']}")
        if client_info.get('empresa'):
            logger.info(f"🏢 Empresa: {client_info['empresa']} ({client_info.get('categoria_empresa', 'N/A')})")
        
        # Log del resumen anterior (lo más importante)
        if client_info.get('resumen_anterior'):
            logger.info("💬 RESUMEN DE CONVERSACIÓN ANTERIOR:")
            logger.info(f"   {client_info['resumen_anterior'][:200]}..." if len(client_info['resumen_anterior']) > 200 else f"   {client_info['resumen_anterior']}")
        
        # Log de acciones
        if client_info.get('acciones_tomadas'):
            logger.info(f"✅ Acciones tomadas: {client_info['acciones_tomadas'][:100]}...")
        if client_info.get('acciones_por_tomar'):
            logger.info(f"📋 Acciones pendientes: {client_info['acciones_por_tomar'][:100]}...")
        
        # Log de información comercial
        if client_info.get('interes_detectado'):
            logger.info(f"🎯 Interés: {client_info['interes_detectado']}")
        if client_info.get('presupuesto_mencionado'):
            logger.info(f"💰 Presupuesto: ${client_info['presupuesto_mencionado']}")
        if client_info.get('es_cliente_recurrente'):
            logger.info(f"⭐ Cliente recurrente: {client_info['es_cliente_recurrente']}")
        if client_info.get('numero_interacciones'):
            logger.info(f"📊 Interacciones previas: {client_info['numero_interacciones']}")
        
        logger.info("=" * 80)
        logger.info("📄 SYSTEM PROMPT COMPLETO (primeros 500 caracteres):")
        logger.info("=" * 80)
        # Mostrar los primeros 500 caracteres del system_content para verificar
        logger.info(system_content[:500] + "..." if len(system_content) > 500 else system_content)
        logger.info("=" * 80)
    else:
        logger.info("💬 Mensaje subsecuente - Contexto disponible en historial de conversación")
    # ========== FIN DEL LOGGING ==========

    # Crear mensaje del sistema
    system_message = {
        "role": "system",
        "content": system_content
    }
    
    # Convertir historial de conversación al formato OpenAI
    messages = [system_message]
    
    for message in conversation_history:
        role = message.get("role")
        content = str(message.get("content", ""))
        
        if role in ["user", "assistant"]:
            messages.append({
                "role": role,
                "content": content
            })
        elif role == "tool":
            # Los mensajes de herramientas se convierten en mensajes del asistente
            messages.append({
                "role": "assistant", 
                "content": content
            })
    
    return messages