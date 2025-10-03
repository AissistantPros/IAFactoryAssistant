import os
import json
from typing import List, Dict, Optional, cast, Any
from decouple import config
from openai import OpenAI

# Fix para config
def get_api_key() -> str:
    """Obtiene la API key con validación de tipo"""
    key = config("CHATGPT_SECRET_KEY", default="")
    if not key:
        raise ValueError("CHATGPT_SECRET_KEY no configurada")
    return str(key)

# 1. Importamos la función para generar el prompt desde tu archivo prompt_text.py
from prompt_text import generate_openai_prompt

# ----- Configuración del Cliente OpenAI y Modelo -----
CLIENT_INIT_ERROR = None
client = None
try:
    print("[aiagent_text.py] Intentando inicializar cliente OpenAI...")
    client = OpenAI(api_key=get_api_key())
except Exception as e_client:
    CLIENT_INIT_ERROR = str(e_client)
    print(f"[aiagent_text.py] ERROR al inicializar OpenAI: {CLIENT_INIT_ERROR}")

# --- Modelo por defecto para texto ---
MODEL_TO_USE = "gpt-4.1-mini"   # tu modelo rápido, ventana grande

# -----  Librerías y utilidades de herramientas -----
from buscarslot import process_appointment_request
from crearcita import create_calendar_event
from editarcita import edit_calendar_event
from eliminarcita import delete_calendar_event
from utils import search_calendar_event_by_phone
from selectevent import select_calendar_event_by_index
from consultarinfo import get_consultorio_data
from weather_utils import get_cancun_weather

def handle_detect_intent(**kwargs) -> Dict:
    return {"intent_detected": kwargs.get("intention")}

# ====== Mapeo de funciones reales (tool name → función Python) ======
def tool_process_appointment_request(
    user_query_for_date_time: str,
    day_param: Optional[int] = None,
    month_param: Optional[Any] = None,
    year_param: Optional[int] = None,
    fixed_weekday_param: Optional[str] = None,
    explicit_time_preference_param: Optional[str] = None,
    is_urgent_param: Optional[bool] = False,
    more_late_param: Optional[bool] = False,
    more_early_param: Optional[bool] = False,
):
    return process_appointment_request(
        user_query_for_date_time=user_query_for_date_time,
        day_param=day_param,
        month_param=month_param,
        year_param=year_param,
        fixed_weekday_param=fixed_weekday_param,
        explicit_time_preference_param=explicit_time_preference_param,
        is_urgent_param=is_urgent_param or False,
        more_late_param=more_late_param or False,
        more_early_param=more_early_param or False,
    )


def tool_create_calendar_event(
    name: str,
    phone: str,
    reason: str,
    start_time: str,
    end_time: str,
):
    return create_calendar_event(
        name=name,
        phone=phone,
        reason=reason,
        start_time=start_time,
        end_time=end_time,
    )


def tool_search_calendar_event_by_phone(phone: str):
    return search_calendar_event_by_phone(phone=phone)


def tool_select_calendar_event_by_index(index: int):
    # Adaptar nombre esperado por la función real
    return select_calendar_event_by_index(selected_index=index)


def tool_edit_calendar_event(
    event_id: str,
    new_start_time_iso: str,
    new_end_time_iso: str,
    new_name: Optional[str] = None,
    new_reason: Optional[str] = None,
    new_phone_for_description: Optional[str] = None,
):
    return edit_calendar_event(
        event_id=event_id,
        new_start_time_iso=new_start_time_iso,
        new_end_time_iso=new_end_time_iso,
        new_name=new_name,
        new_reason=new_reason,
        new_phone_for_description=new_phone_for_description,
    )


def tool_delete_calendar_event(event_id: str, original_start_time_iso: str):
    return delete_calendar_event(event_id=event_id, original_start_time_iso=original_start_time_iso)


tool_functions_map = {
    "process_appointment_request": tool_process_appointment_request,
    "create_calendar_event": tool_create_calendar_event,
    "search_calendar_event_by_phone": tool_search_calendar_event_by_phone,
    "select_calendar_event_by_index": tool_select_calendar_event_by_index,
    "edit_calendar_event": tool_edit_calendar_event,
    "delete_calendar_event": tool_delete_calendar_event,
    "detect_intent": handle_detect_intent,
    "get_cancun_weather": get_cancun_weather,
}

# ═════════════════ UNIFIED TOOLS DEFINITION ══════════════════════
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "process_appointment_request",
            "description": "Analiza la preferencia de fecha/hora del usuario y devuelve slots disponibles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_query_for_date_time": {"type": "string", "description": "Texto exacto del usuario en español"},
                    "day_param": {"type": "integer"},
                    "month_param": {"description": "Mes (string en español o número)"},
                    "year_param": {"type": "integer"},
                    "fixed_weekday_param": {"type": "string"},
                    "explicit_time_preference_param": {"type": "string"},
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
            "description": "Crea una cita en Google Calendar con los datos proporcionados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "reason": {"type": "string"},
                    "start_time": {"type": "string", "description": "ISO datetime"},
                    "end_time": {"type": "string", "description": "ISO datetime"}
                },
                "required": ["name", "phone", "reason", "start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_calendar_event_by_phone",
            "description": "Busca próximas citas por número telefónico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"}
                },
                "required": ["phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_calendar_event_by_index",
            "description": "Selecciona una cita por su índice en la lista mostrada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"}
                },
                "required": ["index"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_calendar_event",
            "description": "Edita una cita existente con nuevos horarios y datos opcionales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "new_start_time_iso": {"type": "string"},
                    "new_end_time_iso": {"type": "string"},
                    "new_name": {"type": "string"},
                    "new_reason": {"type": "string"},
                    "new_phone_for_description": {"type": "string"}
                },
                "required": ["event_id", "new_start_time_iso", "new_end_time_iso"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Elimina una cita existente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "original_start_time_iso": {"type": "string"}
                },
                "required": ["event_id", "original_start_time_iso"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_intent",
            "description": "Detectar la intención general del usuario (pregunta informativa, solicitud de cita, etc.)."
        }
    }
]

# ---------------- FUNCIÓN PRINCIPAL ----------------
async def process_text_message(
    user_id: str,
    current_user_message: str,
    history: List[Dict],
    client_info: Optional[Dict] = None,
) -> Dict:
    """
    Procesa un mensaje de texto usando GPT-4.1-mini + tool-calling nativo.
    Retorna un dict {reply_text:str, status:str}
    """

    conv_id_for_logs = f"conv:{user_id[:4]}…"  # para logs cortos

    if CLIENT_INIT_ERROR:
        print(f"[{conv_id_for_logs}] Cliente OpenAI no iniciado: {CLIENT_INIT_ERROR}")
        return {
            "reply_text": "Ups, el asistente de texto no está disponible en este momento 😕",
            "status": "error_init_openai",
        }

    # 1) Construimos el prompt CON CONTEXTO
    messages_for_api = generate_openai_prompt(
        history, 
        client_info=client_info
    ) + [
        {"role": "user", "content": current_user_message}
    ]

    try:
        print(
            f"[{conv_id_for_logs}] 1ª llamada a GPT con modelo {MODEL_TO_USE}. "
            f"Mensajes: {len(messages_for_api)}"
        )

        # Validar que el cliente esté disponible
        if not client:
            raise ValueError("Cliente OpenAI no inicializado")

        chat_completion = client.chat.completions.create(
            model=MODEL_TO_USE,
            messages=messages_for_api,  # type: ignore
            tools=TOOLS,  # type: ignore
            tool_choice="auto",
            temperature=0.4,        # 0-1 (0 = ultra-determinista)
            max_tokens=512,         # tope de la respuesta
            top_p=0.9,              # nucleus sampling
            presence_penalty=0.3,   # incentiva temas nuevos
            frequency_penalty=0.2,  # evita repeticiones
        )

        response_message = chat_completion.choices[0].message
        tool_calls = response_message.tool_calls

        # 2) ¿Invocó alguna tool?
        if tool_calls:
            print(
                f"[{conv_id_for_logs}] GPT solicitó {len(tool_calls)} tool_call(s): {tool_calls}"
            )

            # Convertir ChatCompletionMessage a dict para el historial
            response_dict = {
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in response_message.tool_calls or []
                ]
            }
            messages_for_api.append(response_dict)  # tool_call en historial
            tool_call = tool_calls[0]
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments or "{}")

            # Detectar petición de finalizar conversación vía tool virtual end_conversation
            if func_name == "end_conversation":
                reason = func_args.get("reason") if isinstance(func_args, dict) else None
                ai_final_response_content = ""
                status_message = "success_end_conversation"
                return {
                    "reply_text": ai_final_response_content,
                    "status": status_message,
                    "end_chat": True,
                    "end_reason": reason or "assistant_requested_end",
                }

            # Ejecutamos la función real con timeout
            if func_name in tool_functions_map:
                try:
                    import asyncio
                    tool_result = await asyncio.wait_for(
                        asyncio.to_thread(tool_functions_map[func_name], **func_args),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    tool_result = {
                        "error": f"timeout_exceeded",
                        "message": f"La operación {func_name} tardó más de 10 segundos"
                    }
                    print(f"[{conv_id_for_logs}] ⏰ TIMEOUT en tool {func_name}")
                except Exception as e_tool:
                    tool_result = {
                        "error": f"tool_execution_error",
                        "message": f"Error ejecutando {func_name}: {str(e_tool)}"
                    }
                    print(f"[{conv_id_for_logs}] ❌ ERROR en tool {func_name}: {e_tool}")
            else:
                tool_result = {"error": f"Función {func_name} no registrada."}
            print(f"[{conv_id_for_logs}] Resultado tool {func_name}: {tool_result}")

            # System message con la respuesta de la tool
            messages_for_api.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": json.dumps(tool_result),
                }
            )

            # 3) Segunda pasada para respuesta final
            # Validar que el cliente esté disponible
            if not client:
                raise ValueError("Cliente OpenAI no inicializado")

            # Segunda llamada al LLM para que formule la respuesta final
            second_chat_completion = client.chat.completions.create(
                model=MODEL_TO_USE,
                messages=messages_for_api,  # type: ignore
                temperature=0.4,
                max_tokens=512,
                top_p=0.9,
            )

            content = second_chat_completion.choices[0].message.content
            ai_final_response_content = (content or "").strip()
            status_message = "success_with_tool"
        else:
            content = response_message.content
            ai_final_response_content = (content or "").strip()
            status_message = "success_no_tool"

        # Detección de final de conversación por marcador explícito del asistente
        end_chat = False
        end_reason = None
        if ai_final_response_content:
            import re
            # Detectar marcador de cierre por texto especial o tool inline
            if ai_final_response_content.strip() == "__END_CHAT__":
                end_chat = True
                ai_final_response_content = ""
                end_reason = "assistant_requested_end"
            else:
                m = re.search(r"\[end_conversation\((.*?)\)\]", ai_final_response_content, flags=re.IGNORECASE)
                if m:
                    end_chat = True
                    # Extraer razón si viene como reason="..."
                    args_str = m.group(1)
                    m_reason = re.search(r"reason\s*=\s*\"([^\"]+)\"", args_str)
                    end_reason = m_reason.group(1) if m_reason else None
                    # Eliminar el marcador del texto visible
                    ai_final_response_content = re.sub(r"\s*\[end_conversation\(.*?\)\]\s*", "", ai_final_response_content, flags=re.IGNORECASE).strip()

        print(
            f"[{conv_id_for_logs}] Respuesta final: '{ai_final_response_content}'"
        )

        result: Dict[str, Any] = {
            "reply_text": ai_final_response_content,
            "status": status_message,
        }
        if end_chat:
            result["end_chat"] = True
            if end_reason:
                result["end_reason"] = end_reason
        return result

    except Exception as e_main_process:
        import traceback
        traceback.print_exc()
        
        # Mensaje más específico según el tipo de error
        error_str = str(e_main_process).lower()
        
        if "rate_limit" in error_str or "429" in error_str:
            return {
                "reply_text": "El sistema está muy ocupado ahora. Por favor intenta en unos segundos 😊",
                "status": "error_rate_limit"
            }
        elif "api_key" in error_str or "authentication" in error_str or "401" in error_str:
            return {
                "reply_text": "Hay un problema de configuración. Por favor contacta al administrador 🔧",
                "status": "error_api_key"
            }
        elif "timeout" in error_str or "timed out" in error_str:
            return {
                "reply_text": "La respuesta tardó demasiado. Por favor intenta de nuevo 🕐",
                "status": "error_timeout"
            }
        elif "connection" in error_str or "network" in error_str:
            return {
                "reply_text": "Parece que hay problemas de conexión. Intenta en un momento 📡",
                "status": "error_connection"
            }
        else:
            return {
                "reply_text": "¡Caramba! 😅 Hubo un problema procesando tu mensaje. "
                "¿Podrías intentar de nuevo?",
                "status": "error_processing_message",
            }