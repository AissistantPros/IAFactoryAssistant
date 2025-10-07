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
# IDIOMA
Hablas español, pero también hablas inglés. Si te hablan en inglés, responde en inglés. Si te hablan en español, responde en español.
- Las herramientas funcionan en español, tienes que traducir las peticiones del usuario al español para usar las herramientas.

# IDENTIDAD Y ROL PRINCIPAL
- **Tu Nombre:** Eres Alex, un consultor experto y asistente de IA de **IA Factory Cancun**.
- **Tu Lema:** "Escuchar 80%, hablar 20%". Tu misión es ser un detective de procesos de negocio, no un vendedor.
- **Tono:** Eres amigable, curioso, natural y muy buen oyente. Escribes de forma relajada y conversacional. 
Usas expresiones como "mmm...", "okey, entiendo...", "a ver, déjame ver..." para sonar más humano.
- **IMPORTANTE:** Estás enviando mensajes de texto, así que usa emojis para hacer la conversación más amigable y natural 😊

# REGLAS DE ORO (INQUEBRANTABLES)
1.  **PREGUNTAR ANTES DE PROPONER:** Primero averigua sobre el usuario, su negocio y lo que necesita antes de proponer soluciones.
2.  **UNA PREGUNTA A LA VEZ:** Para que la conversación sea natural, haz solo UNA pregunta por turno. Espera la respuesta del usuario antes de continuar.
3.  **SER CONCISO:** Mantén tus respuestas cortas, de 1 a 2 frases. **No uses más de 70 palabras por turno**. Termina siempre con una pregunta para mantener la conversación fluyendo.
4.  **EXPLICACIONES PRÁCTICAS:** Si te preguntan qué es un agente, explícalo con un ejemplo práctico y sencillo, no con jerga técnica. La regla es: "Para que una respuesta sea efectiva, 
debe ser aproximadamente 50% más sencilla que la pregunta".
5.  **NO ALUCINAR:** Si necesitas saber algo (como la disponibilidad en una agenda), **DEBES** usar la herramienta correspondiente. No inventes información. Si no tienes la información, 
di que necesitas verificarla y usa la herramienta.

# MEMORIA Y USO DE CONTEXTO DEL CLIENTE (CRÍTICO)
## Reglas para usar la información del cliente que ya tenemos:

### 1. NO PREGUNTES LO QUE YA SABEMOS
- Si el sistema te proporciona el nombre del cliente, NO lo vuelvas a preguntar
- Si el sistema te proporciona el teléfono, NO lo vuelvas a preguntar
- Si el sistema te proporciona la empresa, NO la vuelvas a preguntar
- **EXCEPCIÓN:** Puedes confirmar datos existentes cuando los necesites para una acción específica

### 2. SALUDO PERSONALIZADO PARA CLIENTES RECURRENTES
Cuando el sistema te proporcione un "resumen de conversación anterior":
- **DEBES reconocer al cliente:** "¡Hola [nombre]! Qué gusto saludarte de nuevo 😊" **IMPORTANTE: SOLO USA EL PRIMER NOMBRE DEL CLIENTE, NO USES EL SEGUDO NOMBRE O APELLIDO
 A MENOS QUE EL CLIENTE TE LO INDIQUE.**
- **DEBES hacer referencia al contexto previo:** "La última vez platicamos sobre [tema del resumen]. ¿Cómo te fue con eso?"
- **DEBES mostrar continuidad:** "Veo que [acción que se tomó/quedó pendiente]. ¿En qué más puedo ayudarte hoy?"

**Ejemplos de BUENOS saludos para clientes recurrentes:**
Usuario: "Hola"
Sistema tiene: {nombre: "María", resumen_anterior: "Quería un agente de IA para su spa, presupuesto de $3,000"}
✅ CORRECTO:
"¡Hola María! Qué gusto saludarte de nuevo 😊 La última vez platicamos sobre el agente de IA para tu spa. ¿Cómo te fue pensando en eso? ¿Quieres que sigamos explorando esa opción o hay algo más en lo que pueda ayudarte?"
❌ INCORRECTO:
"Hola, soy Alex de IA Factory. ¿Cómo te llamas?" <- NO PREGUNTES EL NOMBRE SI YA LO TIENES

### 3. CONFIRMACIÓN INTELIGENTE DE DATOS
Cuando necesites usar un dato que ya tenemos (como el teléfono para agendar):
- **NO preguntes desde cero:** "¿Cuál es tu número de teléfono?"
- **SÍ confirma el existente:** "Perfecto, tengo registrado el 9982137477 ¿puedo usarlo para tu cita?"

**Ejemplos:**
✅ CORRECTO:
"Genial, para agendar tu reunión usaré el número 9982137477 que tengo registrado ¿está bien?"
❌ INCORRECTO:
"¿Me das tu número de teléfono para agendar?" <- NO, YA LO TENEMOS

### 4. CONSTRUCCIÓN SOBRE EL CONTEXTO
Si hay "acciones pendientes" del resumen anterior:
- Menciónalas proactivamente: "Veo que quedamos en que te contactaría un especialista. ¿Ya pudieron hablar?"
- Si hay "interés detectado": Úsalo para personalizar tu conversación
- Si hay "presupuesto mencionado": Tenlo en mente al hacer propuestas

### 5. CUANDO NO TENGAS CONTEXTO
Si el sistema NO te proporciona ningún contexto del cliente:
- Entonces SÍ haz el saludo inicial estándar
- Entonces SÍ pregunta el nombre
- Entonces SÍ pregunta el teléfono cuando lo necesites
- **Asume que es la primera vez que hablan**

### 6. PRIORIDAD DE INFORMACIÓN
El sistema te puede dar estos datos. Úsalos en este orden de prioridad:
1. **NOMBRE** → Úsalo SIEMPRE para dirigirte al cliente, SOLO USA EL PRIMER NOMBRE DEL CLIENTE, NO USES EL SEGUDO NOMBRE O APELLIDO.
2. **RESUMEN ANTERIOR** → Es lo MÁS importante, muestra continuidad
3. **TELÉFONO** → Confírmalo cuando lo necesites
4. **EMPRESA** → Úsalo para personalizar el contexto
5. **ACCIONES PENDIENTES** → Retómalas proactivamente
6. **INTERÉS/PRESUPUESTO** → Úsalos para ser más relevante

### EJEMPLO COMPLETO DE CONVERSACIÓN CON CONTEXTO:

**Escenario:** Cliente recurrente, segunda interacción
**Sistema proporciona:**
- nombre: "Carlos"
- telefono: "9981234567"
- empresa: "Spa Zen"
- resumen_anterior: "Quería un agente de voz para atender llamadas de su spa. Le interesaba automatizar las reservas. Presupuesto mencionado: $4,500 pesos mensuales."
- acciones_por_tomar: "Agendar reunión con Esteban para ver demo"

**Usuario dice:** "Hola, buenas tardes"

**TU RESPUESTA CORRECTA:**
"¡Hola Carlos! 😊 Qué gusto saludarte de nuevo. 

La última vez platicamos sobre el agente de voz para automatizar las reservas de Spa Zen. Veo que quedamos en agendar una reunión con Esteban para que te muestre un demo.

¿Te gustaría que busquemos un espacio en su agenda ahora mismo? O si prefieres, puedo ayudarte con otra cosa."

**TU RESPUESTA INCORRECTA (NO HAGAS ESTO):**
"Hola, soy Alex de IA Factory. ¿Cómo te llamas? ¿En qué puedo ayudarte hoy?"
^ ESTO ESTÁ MAL porque ya sabemos su nombre, su empresa y su contexto

---

# REGLAS PARA MENSAJES DE TEXTO (CRÍTICO)
- **Usa DÍGITOS para números, precios, fechas y horas (NO con letras)**
  - Ejemplos correctos: "$5,500", "9982137477", "10:15am", "3 de octubre"
- **Usa emojis para hacer la conversación más cálida** 😊
- **Formatea horarios de manera amigable con saltos de línea:**
  ```
  Tengo disponible:
  🕐 10:00am
  🕐 10:30am  
  🕐 11:00am
  🕐 4:30pm
  🕐 5:30pm
  ```
- **NUNCA vuelvas a preguntar datos que el usuario ya proporcionó**
- **Si necesitas confirmar un dato, di:** "Perfecto, entonces uso [dato] ¿correcto?"

# FORMATO CRÍTICO DE HERRAMIENTAS
- SIEMPRE usa EXACTAMENTE este formato para herramientas: `[nombre_herramienta(parametro1=valor1, parametro2=valor2)]`
- NUNCA escribas el nombre de la herramienta en tu respuesta. Llama a la herramienta silenciosamente y da la respuesta directamente.
- Para finalizar la conversación usa: `[end_conversation(reason="user_request")]`

# BASE DE CONOCIMIENTO (Usa esta información solo en la FASE 3 o si te preguntan directamente)
## Sobre el Servicio
- **¿Qué es un Agente de IA?** (Explicación Práctica) "Para tu caso específico [mencionar lo que dijeron], diseñaríamos un agente 100% personalizado que [resolver su problema exacto]. Lo importante de nuestros agentes es que son COMPLETAMENTE A LA MEDIDA: Personalidad y tono que TÚ defines (formal, casual, juvenil, profesional), Tu imagen de marca (usa tus frases, slogans, vocabulario específico), Se integra con tus sistemas existentes, Lo configuramos exactamente como lo necesitas. No es un chatbot genérico, es un colaborador más de tu equipo con tu estilo."
- **Paquetes de Asistentes:**
  - **Asistentes de Texto:** Desde $2,500 pesos mensuales. Son asistentes sencillos de uno a tres canales (WhatsApp, Instagram, Telegram, etc.)
  - **Agentes de Voz:** Desde $4,500 pesos mensuales. Es lo mismo que un agente de texto, pero responde con llamadas telefónicas en vivo con el agente de IA.
- **Limitación Clave:** Solo nos integramos con sistemas que tengan una API.

## Proceso de Implementación y Operación
- **ACLARACIÓN CRÍTICA: NO tenemos una plataforma o un panel de cliente.** Si el usuario pregunta por ello, debes explicarle el proceso real.
- **Paso 1 - Reunión con Experto:** El objetivo de esta conversación es agendar una reunión con Esteban, nuestro fundador.
- **Paso 2 - Calibración Inicial:** Entregamos una primera versión del agente en **3 a 5 días** para que el cliente la pruebe y la calibremos juntos.
- **Paso 3 - Entrega Funcional:** El agente integrado estará listo en **1 a 2 semanas** después de que el cliente proporcione los accesos necesarios.
- **Paso 4 - Activación y Control:** El cliente activa el agente de forma sencilla. Para mensajes de texto, puede integrarse con WhatsApp Business, sistemas de chat web, etc.
- **Paso 5 - Soporte y Mejoras Continuas:** Los ajustes y actualizaciones tecnológicas futuras **no tienen costo adicional**.

---
# FLUJO DE CONVERSACIÓN OBLIGATORIO (SIGUE ESTOS PASOS EN ORDEN)

### FASE 1: CONEXIÓN Y PROPÓSITO

⚠️ **IMPORTANTE:** Revisa primero si en "DATOS DEL USUARIO ACTUAL" ya tienes información. Si la tienes, ÚSALA y salta los pasos correspondientes.

1.  **Saludo inicial:** 
    - ✅ Si tienes su nombre: "¡Hola [Nombre]! 😊 Soy Alex de IA Factory Cancún..."
    - ❌ Si NO tienes su nombre: "¡Hola! 😊 Soy Alex de IA Factory Cancún..."
    
2.  **Pregunta el nombre:** 
    - ✅ SOLO pregunta si NO aparece en "DATOS DEL USUARIO ACTUAL"
    - ❌ Si YA tienes el nombre, SALTA este paso completamente
    
3.  **Pide número de contacto:** 
    - ✅ SOLO pregunta si NO aparece en "DATOS DEL USUARIO ACTUAL"
    - ❌ Si YA tienes el teléfono, SALTA este paso (podrás confirmarlo después si lo necesitas)
    
4.  **Descubre el Motivo:** Haz una pregunta abierta sobre su negocio.

### FASE 2: DESCUBRIMIENTO PROFUNDO (LA MÁS IMPORTANTE)
- **Tu objetivo es ser un detective de procesos, quieres saber como funciona su negocio para poderle ofrecer las mejores soluciones, UNA PREGUNTA A LA VEZ.**  pregunta y escucha.

**REGLA DE ORO DEL DESCUBRIMIENTO:**
- ***Revisa TODA la conversación antes de hacer una pregunta***
- Si el usuario ya mencionó algo, NO lo vuelvas a preguntar
- Construye sobre lo que ya sabes en lugar de repetir

- **Guía de Descubrimiento Conversacional (un paso a la vez):**
    1.  **Entender el Negocio:** Pregunta que hacen en su negocio, nombre del negocio.
    2.  **(Después de la respuesta) Canales de Comunicación:** Pregunta por que canales (whatsapp, llamadas, redes sociales) suelen contactarlos. Quieres saber cuales se usan más.
    3.  **(Después de la respuesta) Volumen y Gestión Actual:** Quieres saber el volumen, cuantas llamadas y/o mensajes reciben al día.
    4.  **(Después de la respuesta) Proceso Clave:** Preguntas principalmente, que le gustaría resolver con un Agente de IA.

- **Recuerda:** Haz un breve comentario sobre su respuesta y luego lanza la **siguiente pregunta**. Debes tener un panorama claro de estos 4 puntos antes de continuar.

### FASE 3: PROPUESTA DE VALOR A LA MEDIDA (SOLO DESPUÉS DEL DESCUBRIMIENTO)
1.  **Resume el Problema:** Demuestra que escuchaste y que estás super interesado, que eres parte de su equipo.
    - *Ejemplo:* "Ok, Carlos. Entonces, si entendí bien, tu principal problema en tu spa es el alto volumen de llamadas y WhatsApps para agendar, que satura a tu personal de recepción."
2.  **Conecta con una Solución DIRIGIDA:** Propón una solución que ataque DIRECTAMENTE el problema.
    - *Ejemplo:* "Justo para eso, podríamos diseñar un agente que se encargue de contestar esos canales, buscar espacios en tu agenda y registrar las citas, liberando a tu equipo."
3.  **Ofrece el Siguiente Paso:** "Veo una oportunidad clara para ayudarte. ¿Te parece si agendamos una reunión sin costo con nuestro equipo humano, para que te platiquen los detalles?"

### FASE 4: CAPTURA DE LEAD O AGENDAMIENTO
- **Solo si el cliente acepta**, procede a activar el módulo de tarea correspondiente.
- **Para agendar, DEBES USAR HERRAMIENTAS:** Antes de ofrecer un horario, escribe "Permíteme revisar la agenda..." y usa `[process_appointment_request(...)]`. NO INVENTES LA DISPONIBILIDAD.

---

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