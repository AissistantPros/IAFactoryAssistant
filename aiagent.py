# aiagent.py
# -*- coding: utf-8 -*-
"""
Motor de Decisión (Versión Final de Producción para Groq/Llama 3.3)
"""
import asyncio
import json
import logging
import re
import shlex
import time
from time import perf_counter
from typing import Dict, List, Any, Optional, Callable

from decouple import config
from groq import AsyncGroq

# Importamos nuestro motor de prompts final del paso anterior
from prompt import LlamaPromptEngine
from weather_utils import get_cancun_weather

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)5s | %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("aiagent")

# --- Clientes y Gestores ---
try:
    api_key = config("GROQ_API_KEY", default=None)
    if not api_key:
        raise ValueError("GROQ_API_KEY no está configurada")
    client = AsyncGroq(api_key=str(api_key))
    logger.info("Cliente AsyncGroq inicializado correctamente.")
except Exception as e:
    logger.critical(f"No se pudo inicializar el cliente Groq. Verifica GROQ_API_KEY: {e}")
    client = None

class SessionManager:
    """Gestiona el estado de la conversación para cada sesión única."""
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_state(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {"mode": None}
        return self.sessions[session_id]

    def set_mode(self, session_id: str, mode: str):
        state = self.get_state(session_id)
        state['mode'] = mode

# --- Motor de Herramientas con Parsing Seguro ---
class ToolEngine:
    """Encapsula el parseo, validación y ejecución de herramientas."""
    # Patrones para detectar diferentes formatos
    TOOL_CALL_PATTERN = re.compile(r'\[(\w+)\((.*?)\)\]', re.DOTALL)
    TOOL_CALL_NO_ARGS_PATTERN = re.compile(r'\[(\w+)\]', re.DOTALL)  # NUEVO: acepta [toolname]
    JSON_PATTERN = re.compile(r'\{[^{}]*"type"\s*:\s*"function"[^{}]*\}', re.DOTALL)
    XML_PATTERN = re.compile(r'<function\s*=\s*(\w+)>(.*?)</function>', re.DOTALL)
    PYTHON_TAG_PATTERN = re.compile(r'<\|python_tag\|>\s*(\w+)\.call\((.*?)\)', re.DOTALL)

    def __init__(self, tool_definitions: List[Dict]):
        self.tool_schemas = {tool['function']['name']: tool['function'] for tool in tool_definitions}
        self.tool_executors = self._map_executors()
        self._buffer = ""
        self._buffer_start_time = None
        self._buffer_timeout = 0.5  # 500ms

    def _map_executors(self) -> Dict[str, Callable]:
        """Mapea nombres de herramientas a las funciones de Python."""
        # Importaciones de tu lógica de negocio
        from registrar_lead import registrar_lead
        from crearcita import create_calendar_event
        from editarcita import edit_calendar_event
        from eliminarcita import delete_calendar_event
        from utils import search_calendar_event_by_phone
        import buscarslot

        return {
            "registrar_lead": registrar_lead,
            "process_appointment_request": buscarslot.process_appointment_request,
            "create_calendar_event": create_calendar_event,
            "edit_calendar_event": edit_calendar_event,
            "delete_calendar_event": delete_calendar_event,
            "search_calendar_event_by_phone": search_calendar_event_by_phone,
            "end_call": self._handle_end_call,
        }

    
    def _handle_end_call(self, reason: str = "user_request") -> Dict:
        """Marca que se debe terminar la llamada."""
        # Agregar una bandera especial que el sistema reconozca
        return {"action": "end_call", "reason": reason, "__terminate__": True}

    def parse_tool_calls(self, text: str) -> List[Dict]:
        """Parsea el texto crudo del LLM y extrae las llamadas a herramientas."""
        tool_calls = []
        
        # FIX: Detectar alucinación de end_call
        if 'end_call({"reason"' in text and '[end_call' not in text:
            logger.warning("⚠️ Detectada alucinación de end_call sin corchetes")
            # Convertir al formato correcto
            text = text.replace('end_call({"reason": "user_request"})', '[end_call(reason="user_request")]')
            text = text.replace('end_call({"reason": "no_response"})', '[end_call(reason="no_response")]')
        
        # Intentar con todos los formatos
        # 1. Formato preferido [tool(args)]
        for match in self.TOOL_CALL_PATTERN.finditer(text):
            tool_name, args_str = match.groups()
            if tool_name in self.tool_schemas:
                try:
                    args = self._parse_arguments_with_shlex(args_str)
                    tool_calls.append({"name": tool_name, "arguments": args})
                except Exception as e:
                    logger.warning(f"Error parseando argumentos para '{tool_name}': {e}")
        # 1b. NUEVO: Formato [toolname] sin paréntesis ni argumentos
        for match in self.TOOL_CALL_NO_ARGS_PATTERN.finditer(text):
            tool_name = match.group(1)
            # Solo agregar si no fue ya detectado con paréntesis
            if tool_name in self.tool_schemas and not any(tc["name"] == tool_name for tc in tool_calls):
                tool_calls.append({"name": tool_name, "arguments": {}})
        
        # 2. Formato JSON (el problemático)
        for match in self.JSON_PATTERN.finditer(text):
            try:
                json_obj = json.loads(match.group(0))
                if json_obj.get("type") == "function" and json_obj.get("name") in self.tool_schemas:
                    tool_calls.append({
                        "name": json_obj["name"],
                        "arguments": json_obj.get("parameters", {})
                    })
            except Exception as e:
                logger.warning(f"Error parseando JSON de herramienta: {e}")
        
        # 3. Formato XML
        for match in self.XML_PATTERN.finditer(text):
            tool_name = match.group(1)
            if tool_name in self.tool_schemas:
                try:
                    args_json = match.group(2)
                    args = json.loads(args_json) if args_json.strip() else {}
                    tool_calls.append({"name": tool_name, "arguments": args})
                except Exception as e:
                    logger.warning(f"Error parseando XML para '{tool_name}': {e}")
        
        # 4. Formato python_tag
        for match in self.PYTHON_TAG_PATTERN.finditer(text):
            tool_name = match.group(1)
            if tool_name in self.tool_schemas:
                try:
                    args = self._parse_arguments_with_shlex(match.group(2))
                    tool_calls.append({"name": tool_name, "arguments": args})
                except Exception as e:
                    logger.warning(f"Error parseando python_tag para '{tool_name}': {e}")
        
        return tool_calls
    
    def _parse_arguments_with_shlex(self, args_str: str) -> Dict[str, Any]:
        """
        Parsea argumentos de forma segura usando shlex y limpia comas finales de los valores.
        """
        if not args_str.strip():
            return {}
            
        args = {}
        try:
            # shlex.split maneja correctamente las comillas y espacios
            parts = shlex.split(args_str)
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    args[key.strip()] = self._convert_type(value)
        except Exception as e:
            print(f"Advertencia: Error en shlex parsing: {e}, intentando parsing simple")
            for pair in args_str.split(','):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    args[key.strip()] = self._convert_type(value.strip())

        cleaned_args = {}
        for key, value in args.items():
            if isinstance(value, str):
                value = value.rstrip(',')
            cleaned_args[key] = value
        return cleaned_args
    
    def _convert_type(self, value: str) -> Any:
        """Convierte un string a su tipo Python más probable."""
        value = value.strip().strip('"\'')
        if value.lower() == 'true': return True
        if value.lower() == 'false': return False
        if value.lower() in ('none', 'null'): return None
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    async def execute_tool(self, tool_call: Dict) -> Dict:
        """Ejecuta una herramienta y devuelve un resultado estructurado."""
        tool_name = tool_call["name"]
        arguments = tool_call["arguments"]
        executor = self.tool_executors.get(tool_name)
        
        if not executor:
            return {"error": f"Herramienta desconocida: {tool_name}", "details": "El ejecutor no fue encontrado."}
        
        t_start = perf_counter()
        try:
            logger.info(f"Ejecutando: {tool_name} con {arguments}")
            if asyncio.iscoroutinefunction(executor):
                result = await executor(**arguments)
            else:
                result = executor(**arguments)
            
            t_end = perf_counter()
            logger.info(f"[PERF] Herramienta '{tool_name}' ejecutada en {(t_end - t_start) * 1000:.1f} ms")
            
            return result
        except Exception as e:
            logger.exception(f"La ejecución de la herramienta '{tool_name}' falló.")
            return {
                "error": f"Fallo en la ejecución de {tool_name}",
                "details": str(e),
                "arguments_used": arguments
            }

    def remove_tool_patterns(self, text: str) -> str:
        """Elimina TODOS los patrones de herramientas del texto."""
        text = self.TOOL_CALL_PATTERN.sub('', text)
        text = self.JSON_PATTERN.sub('', text)
        text = self.XML_PATTERN.sub('', text)
        text = self.PYTHON_TAG_PATTERN.sub('', text)
        
        # FIX: Eliminar también la alucinación de end_call
        text = re.sub(r'end_call\s*\(\s*\{[^}]*\}\s*\)', '', text)
        
        return text.strip()

# --- Agente Principal de IA (Orquestador) ---
class AIAgent:
    def __init__(self, tool_definitions: List[Dict]):
        self.groq_client = client
        self.prompt_engine = LlamaPromptEngine(tool_definitions=tool_definitions)
        self.tool_engine = ToolEngine(tool_definitions)
        self.session_manager = SessionManager()
        self.model = "llama-3.3-70b-versatile"




   
    async def process_stream(self, session_id: str, history: List[Dict]) -> str:
        """Orquesta el flujo completo en un solo pase de streaming."""
        from state_store import emit_latency_event
        
        # Obtenemos el estado de la sesión, que puede contener el 'mode' (crear, editar, etc.)
        session_state = self.session_manager.get_state(session_id)
        current_mode = session_state.get("mode") # Esto será 'crear', 'editar', o None
        
        # Obtener clima de Cancún para el system message
        clima = get_cancun_weather()
        # Extraer y formatear datos del clima correctamente
        if 'cancun_weather' in clima and 'current' in clima['cancun_weather']:
            current = clima['cancun_weather']['current']
            clima_contextual = f"""El clima en Cancún es:
Temperatura: {current.get('temperature', 'N/A')}
Sensación térmica: {current.get('feels_like', 'N/A')}
Condición: {current.get('description', 'N/A')}
Humedad: {current.get('humidity', 'N/A')}
Velocidad del viento: {current.get('wind_speed', 'N/A')}"""
        else:
            # Si hay error, usar mensaje genérico
            clima_contextual = "Información del clima no disponible en este momento."
        # Generar el prompt pasándole el clima contextual
        full_prompt = self.prompt_engine.generate_prompt(history, current_mode, clima_contextual=clima_contextual)
        
        emit_latency_event(session_id, "chunk_received")

        # El resto de la función (el bloque 'try...except' para llamar a Groq) sigue igual...
        try:
            # Medición de latencia de la IA
            logger.info(f"[PERF] Iniciando llamada a Groq (modelo: {self.model})")
            t_start_llm = perf_counter()
            first_chunk_time = None

            if self.groq_client is None:
                raise Exception("Cliente Groq no está inicializado")

            stream = await self.groq_client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.7,  # Más conversacional
                stream=True
            )
            full_response_text = ""
            async for chunk in stream:
                if first_chunk_time is None:
                    first_chunk_time = perf_counter()
                    ttft = (first_chunk_time - t_start_llm) * 1000
                    logger.info(f"[PERF] IA (Groq) - Time To First Token: {ttft:.1f} ms")
                
                full_response_text += chunk.choices[0].delta.content or ""
        except Exception as e:
            logger.error(f"Error en la llamada a Groq: {e}")
            return "Lo siento, hay un problema con la conexión al asistente. Por favor, intente de nuevo."

        emit_latency_event(session_id, "parse_start")
        
        # Parseo de la respuesta
        t_parse_start = perf_counter()
        user_facing_text = self.tool_engine.remove_tool_patterns(full_response_text).strip()
        tool_calls = self.tool_engine.parse_tool_calls(full_response_text)
        t_parse_end = perf_counter()
        logger.info(f"[PERF] Parsing de respuesta del LLM en {(t_parse_end - t_parse_start) * 1000:.1f} ms")
        
        # --- INICIO: DETECCIÓN DE SOLICITUD DE TELÉFONO ---
        phone_request_patterns = [
            "número",
            "teléfono",
            "celular",
            "whatsapp",
            "contacto"
        ]
        if any(pattern in user_facing_text.lower() for pattern in phone_request_patterns):
            # Activar modo captura de teléfono
            if hasattr(self, 'conversation_flow') and self.conversation_flow:
                self.conversation_flow.set_phone_capture_mode(True)
                logger.info("📞 Detectada solicitud de número telefónico - activando pausa extendida")
        # Detectar si ya se recibió un número (10 dígitos consecutivos)
        import re
        if re.search(r'\b\d{10}\b', " ".join([msg.get("content", "") for msg in history[-3:]])):
            # Desactivar modo captura
            if hasattr(self, 'conversation_flow') and self.conversation_flow:
                self.conversation_flow.set_phone_capture_mode(False)
                logger.info("✅ Número telefónico capturado - restaurando pausa normal")
        # --- FIN: DETECCIÓN DE SOLICITUD DE TELÉFONO ---

        if tool_calls:
            emit_latency_event(session_id, "tool_detected", {"count": len(tool_calls)})
            
            # Ejecución de herramientas
            emit_latency_event(session_id, "tool_exec_start")
            tool_tasks = [self.tool_engine.execute_tool(tc) for tc in tool_calls]
            results = await asyncio.gather(*tool_tasks)
            emit_latency_event(session_id, "tool_exec_end")
            
            # NO agregar al historial aquí todavía

            for tool_call, result in zip(tool_calls, results):
                tool_content = json.dumps(result, ensure_ascii=False)
                history.append({
                    "role": "tool", 
                    "name": tool_call["name"],
                    "content": tool_content
                })
                logger.info(f"[HISTORIAL] Agregado 'tool' ({tool_call['name']}): {tool_content[:200]}...")
            

            # Verificar si alguna herramienta pidió terminar la llamada
            for result in results:
                if isinstance(result, dict) and result.get("__terminate__"):
                    # Agregar SOLO UNA VEZ antes de terminar
                    history.append({"role": "assistant", "content": full_response_text})
                    logger.info("[HISTORIAL] IA solicitó terminar llamada")
                    return "__END_CALL__"

            # Generación de respuesta sintética si es necesario
            if not user_facing_text:
                from synthetic_responses import generate_synthetic_response
                if tool_calls and results:
                    # Verificar si hubo error en la herramienta
                    first_result = results[0]
                    if isinstance(first_result, dict) and "error" in first_result:
                        # Usar status del error si existe, sino "error" genérico
                        error_status = first_result.get("status", "error")
                        user_facing_text = generate_synthetic_response(
                            tool_calls[0]["name"], 
                            {"status": error_status}
                        )
                    else:
                        user_facing_text = generate_synthetic_response(
                            tool_calls[0]["name"], 
                            first_result
                        )
                    logger.info(f"[HISTORIAL] Respuesta sintética generada: '{user_facing_text}'")
                else:
                    user_facing_text = "He procesado su solicitud."
            
            # Agregar SOLO UNA VEZ la respuesta final de la IA
            history.append({"role": "assistant", "content": user_facing_text})
            logger.info(f"[HISTORIAL] Agregado 'assistant' con respuesta final: '{user_facing_text}'")
        else:
            # Logueo del historial para respuestas directas
            history.append({"role": "assistant", "content": user_facing_text})
            logger.info(f"[HISTORIAL] Agregado 'assistant' con respuesta de texto: '{user_facing_text}'")
        
        emit_latency_event(session_id, "response_complete")
        return user_facing_text


# El resto del archivo no cambia, pero lo incluyo para que sea completo
# --- Definiciones Completas de Herramientas ---
ALL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_mode",
            "description": "Cambia el modo de operación del asistente para activar un flujo de tarea específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["capturar_lead", "crear_cita", "editar_cita", "eliminar_cita", "None"],
                        "description": "'capturar_lead' para registrar un cliente, 'crear_cita' para agendar, 'editar_cita' para modificar, 'eliminar_cita' para cancelar, 'None' para modo general."
                    }
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "Cierra la conversación de manera definitiva.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_lead",
            "description": "Registra la información de un nuevo cliente potencial.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "empresa": {"type": "string"},
                    "telefono": {"type": "string"}
                },
                "required": ["nombre", "empresa", "telefono"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_appointment_request",
            "description": "Procesa la solicitud de agendamiento o consulta de disponibilidad de citas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_query_for_date_time": {"type": "string"},
                    "day_param": {"type": "integer"},
                    "month_param": {"type": ["string", "integer"]},
                    "year_param": {"type": "integer"},
                    "fixed_weekday_param": {"type": "string"},
                    "explicit_time_preference_param": {"type": "string", "enum": ["mañana", "tarde", "mediodia"]},
                    "is_urgent_param": {"type": "boolean"},
                    "more_late_param": {"type": "boolean"},
                    "more_early_param": {"type": "boolean"}
                },
                "required": ["user_query_for_date_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Crear una nueva cita en el calendario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "reason": {"type": "string"},
                    "start_time": {"type": "string", "format": "date-time"},
                    "end_time": {"type": "string", "format": "date-time"}
                },
                "required": ["name", "phone", "start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_calendar_event_by_phone",
            "description": "Buscar citas existentes por número de teléfono."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_calendar_event",
            "description": "Modificar una cita existente en el calendario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "new_start_time_iso": {"type": "string", "format": "date-time"},
                    "new_end_time_iso": {"type": "string", "format": "date-time"}
                },
                "required": ["event_id", "new_start_time_iso", "new_end_time_iso"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Eliminar/Cancelar una cita existente del calendario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "original_start_time_iso": {"type": "string", "format": "date-time"}
                },
                "required": ["event_id", "original_start_time_iso"]
            }
        }
    }
]

# Instancia global del agente
ai_agent = AIAgent(tool_definitions=ALL_TOOLS)

async def generate_ai_response(session_id: str, history: List[Dict]) -> str:
    """Función pública que será llamada desde tw_utils.py."""
    return await ai_agent.process_stream(session_id, history)