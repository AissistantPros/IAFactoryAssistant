# main.py
# -*- coding: utf-8 -*-
"""
🚀 PUNTO DE ENTRADA PRINCIPAL
==============================
FastAPI app que maneja:
- Llamadas de voz vía Twilio WebSocket
- Mensajes de texto vía webhook
- APIs REST para herramientas

Usa la nueva arquitectura modular en lugar del monolítico tw_utils.
"""

import os
import asyncio
import logging
import json
import traceback
from typing import Optional, Union, List, Dict, Any
from fastapi import FastAPI, Response, WebSocket, Body, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import httpx
from datetime import datetime

# === TWILIO IMPORTS ===
from twilio.jwt.client import ClientCapabilityToken

# === NUEVA ARQUITECTURA ===
from call_orchestrator import CallOrchestrator

# === MÓDULOS EXISTENTES ===
from consultarinfo import router as consultorio_router
from aiagent_text import process_text_message
import buscarslot
from crearcita import create_calendar_event
from editarcita import edit_calendar_event
from eliminarcita import delete_calendar_event
from selectevent import select_calendar_event_by_index
from utils import search_calendar_event_by_phone

# ===== CONFIGURACIÓN DE LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)5s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger(__name__)

# Silenciar logs verbosos
for noisy_module in [
    "httpcore.http11",
    "httpcore.connection", 
    "httpx",
    "websockets.client",
    "websockets.server",
    "urllib3.connectionpool",
    "asyncio",
    "uvicorn.access",
    "deepgram.clients.common.v1.abstract_async_websocket",
    "twilio.http_client",
]:
    logging.getLogger(noisy_module).setLevel(logging.WARNING)

# ===== FASTAPI APP =====
app = FastAPI(title="AI Assistant Backend")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://iafactorycancun.com",
        "https://www.iafactorycancun.com",
        "https://iafactory.webstudio.is",
        "https://*.webstudio.is",
        "http://localhost:3000",
        "http://localhost:5173",
        "*"  # Temporalmente permitir todos mientras probamos
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# ===== VARIABLES DE ENTORNO TWILIO =====
TWIML_APP_SID = os.getenv("TWIML_APP_SID")
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# ===== RATE LIMITING =====
# Rate limiting global: máximo 15 llamadas totales por día
global_call_limiter = {
    "count": 0,
    "first_call": None,
    "last_reset": None
}

# ===== ESTADO GLOBAL =====
conversation_histories: Dict[str, List[Dict]] = {}
full_conversation_histories: Dict[str, List[Dict]] = {}

# ===== ESTADO DE CHATS DE TEXTO (TIMEOUTS/PULSOS) =====
TEXT_CHAT_STATE: Dict[str, Dict[str, Any]] = {}

# ===== RUTAS =====
app.include_router(consultorio_router, prefix="/api_v1")


@app.on_event("startup")
async def startup_event():
    """
    🚀 Inicialización al arrancar el servidor
    """
    t0 = time.perf_counter()
    # Crear directorios necesarios
    os.makedirs("audio", exist_ok=True)
    os.makedirs("audio_debug", exist_ok=True)
    
    # Pre-cargar datos en caché
    try:
        buscarslot.load_free_slots_to_cache()
    except Exception as e:
        logger.warning(f"Error pre-cargando datos: {e}")
    
    logger.info("🚀 Backend iniciado - Nueva arquitectura modular activa")
    logger.info(f"[LATENCIA] Backend startup completado en {1000*(time.perf_counter()-t0):.1f} ms")

    # Iniciar monitor de chats de texto (pulsos a 20 min, cierre a 60 min)
    try:
        asyncio.create_task(_background_text_chat_monitor())
        logger.info("💬 Monitor de chats de texto iniciado")
    except Exception as e:
        logger.error(f"No se pudo iniciar el monitor de chats de texto: {e}")


@app.get("/")
async def root():
    """Endpoint de salud básico"""
    return {
        "message": "AI Assistant Backend activo",
        "version": "2.0",
        "architecture": "modular"
    }


# ========== ENDPOINTS DE VOZ (TWILIO) ==========

@app.post("/twilio-voice")
async def twilio_voice():
    """
    📞 Endpoint que Twilio llama cuando entra una llamada
    
    Responde con TwiML que abre un Stream hacia nuestro WebSocket
    """
    logger.info("[FUNCIONALIDAD] Nueva llamada entrante (POST /twilio-voice)")
    t0 = time.perf_counter()
    
    # TwiML para iniciar streaming
    twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream name="AudioStream" url="wss://iafactoryassistant.onrender.com/twilio-websocket" track="inbound_track">
      <Parameter name="content-type" value="audio/x-mulaw;rate=8000;channels=1"/>
    </Stream>
  </Connect>
</Response>"""
    
    logger.info(f"[LATENCIA] Respuesta TwiML generada en {1000*(time.perf_counter()-t0):.1f} ms")
    return Response(content=twiml_response, media_type="application/xml")


@app.websocket("/twilio-websocket")
async def twilio_websocket(websocket: WebSocket):
    """
    🎙️ WebSocket que recibe audio en tiempo real de Twilio
    
    Usa el nuevo CallOrchestrator en lugar del viejo TwilioWebSocketManager
    """
    logger.info("[FUNCIONALIDAD] WebSocket /twilio-websocket aceptado")
    t0 = time.perf_counter()
    orchestrator = CallOrchestrator()
    await orchestrator.handle_call(websocket)
    logger.info(f"[LATENCIA] WebSocket /twilio-websocket completado en {1000*(time.perf_counter()-t0):.1f} ms")


@app.get("/api/twilio-token")
async def get_twilio_token(request: Request):
    """
    🔑 Genera un token de acceso para Twilio Voice SDK
    con rate limiting global (máximo 15 llamadas por día)
    """
    logger.info("[FUNCIONALIDAD] Solicitud de token Twilio (GET /api/twilio-token)")
    t0 = time.perf_counter()
    
    # Verificar que tengamos las variables necesarias
    if not TWIML_APP_SID or not ACCOUNT_SID or not AUTH_TOKEN:
        logger.error("Faltan variables de entorno de Twilio")
        raise HTTPException(status_code=500, detail="Configuración incompleta")
    
    # Obtener IP del cliente para logging
    client_ip = request.client.host
    current_time = time.time()
    
    # Rate limiting global - máximo 15 llamadas por día
    if global_call_limiter["last_reset"] is None:
        # Primera llamada del día
        global_call_limiter["count"] = 0
        global_call_limiter["first_call"] = current_time
        global_call_limiter["last_reset"] = current_time
    else:
        # Verificar si ha pasado un día (86400 segundos = 24 horas)
        if current_time - global_call_limiter["last_reset"] > 86400:
            # Reset diario
            global_call_limiter["count"] = 0
            global_call_limiter["first_call"] = current_time
            global_call_limiter["last_reset"] = current_time
            logger.info("🔄 Rate limiting global reseteado - nuevo día")
        elif global_call_limiter["count"] >= 15:
            logger.warning(f"🚫 Límite global diario excedido (15 llamadas) - IP: {client_ip}")
            raise HTTPException(
                status_code=429, 
                detail="Límite diario global excedido (15 llamadas). Intenta mañana."
            )
    
    # Incrementar contador global
    global_call_limiter["count"] += 1
    
    # Generar token
    capability = ClientCapabilityToken(ACCOUNT_SID, AUTH_TOKEN)
    
    # Permitir llamadas salientes usando tu TwiML App
    capability.allow_client_outgoing(TWIML_APP_SID)
    
    # Token válido por 1 hora
    token = capability.to_jwt(ttl=3600)
    
    logger.info(f"Token generado para IP: {client_ip} (llamada #{global_call_limiter['count']}/15 del día)")
    logger.info(f"[LATENCIA] Token Twilio generado en {1000*(time.perf_counter()-t0):.1f} ms")
    
    return {
        "token": token.decode('utf-8') if isinstance(token, bytes) else token,
        "expires_in": 3600,
        "calls_today": global_call_limiter["count"],
        "remaining_calls": 15 - global_call_limiter["count"],
        "limit_type": "global_daily"
    }


# ========== ENDPOINTS DE TEXTO (WEBHOOKS) ==========

class N8NMessage(BaseModel):
    """Modelo para mensajes entrantes de n8n - ESTRUCTURA ACTUALIZADA"""
    # Campos de nivel raíz
    session_id: str
    user_message: str
    canal: str
    timestamp: Optional[str] = None
    origen_url: Optional[str] = None
    
    # Perfil del usuario (anidado)
    user_profile: Optional[Dict[str, Any]] = None
    
    # Info de plataforma (anidado)
    plataforma_info: Optional[Dict[str, Any]] = None
    
    # Contexto de DB (anidado)
    contexto_db: Optional[Dict[str, Any]] = None


def clean_null_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Elimina recursivamente todos los campos con valor None, null, o strings vacíos
    de un diccionario, incluyendo diccionarios anidados.
    
    Args:
        data: Diccionario a limpiar
        
    Returns:
        Diccionario sin valores null/None/vacíos
    """
    if not isinstance(data, dict):
        return data
    
    cleaned = {}
    for key, value in data.items():
        # Saltar valores None o strings vacíos
        if value is None or value == "":
            continue
        
        # Si es un dict, limpiar recursivamente
        if isinstance(value, dict):
            cleaned_nested = clean_null_values(value)
            # Solo agregar si el dict limpio no está vacío
            if cleaned_nested:
                cleaned[key] = cleaned_nested
        # Si es una lista, limpiar cada elemento
        elif isinstance(value, list):
            cleaned_list = [
                clean_null_values(item) if isinstance(item, dict) else item 
                for item in value if item is not None and item != ""
            ]
            if cleaned_list:
                cleaned[key] = cleaned_list
        else:
            cleaned[key] = value
    
    return cleaned


@app.post("/webhook/n8n_message")
async def receive_n8n_message(message_data: N8NMessage):
    """
    💬 Webhook para mensajes de texto desde n8n - VERSIÓN ACTUALIZADA
    """
    # ===== PASO 1: EXTRAER DATOS BÁSICOS =====
    conversation_id = message_data.session_id
    current_message = message_data.user_message
    canal = message_data.canal
    
    # Extraer user_id del perfil o usar default
    user_id = "unknown_user"
    if message_data.user_profile:
        user_id = message_data.user_profile.get("user_id_canal") or user_id
    
    logger.info(f"📱 [USUARIO] {user_id}: '{current_message}'")
    t0 = time.perf_counter()
    
    # ===== PASO 2: LIMPIAR NULLS DE TODA LA DATA =====
    # Convertir el modelo a dict y limpiar nulls
    raw_data = message_data.dict()
    cleaned_data = clean_null_values(raw_data)
    
    logger.debug(f"🧹 Datos limpiados - Campos antes: {len(raw_data)}, después: {len(cleaned_data)}")
    
    # ===== PASO 3: DETERMINAR SI ES PRIMERA INTERACCIÓN =====
    is_first_interaction = conversation_id not in conversation_histories
    
    # ===== PASO 4: INICIALIZAR ESTADO SI ES PRIMERA INTERACCIÓN =====
    if is_first_interaction:
        logger.info(f"🆕 Primera interacción para {conversation_id}")
        conversation_histories[conversation_id] = []
        full_conversation_histories[conversation_id] = []
        
        # Inicializar estado completo
        TEXT_CHAT_STATE[conversation_id] = {
            "first_message_ts": time.time(),
            "last_activity_ts": time.time(),
            "pulse_sent": False,
            "ended": False,
            "canal": canal,
            "metadata": cleaned_data.get("user_profile", {}),
            "plataforma_info": cleaned_data.get("plataforma_info", {}),
            "client_info": {},  # Se llenará abajo
            "message_count": {"user": 0, "assistant": 0},
            "word_count": {"user": 0, "assistant": 0},
            "origen_url": cleaned_data.get("origen_url"),
            "timestamp_inicio": cleaned_data.get("timestamp")
        }
        
        # ===== PASO 5: CONSTRUIR CLIENT_INFO DESDE CONTEXTO_DB =====
        # SOLO en primera interacción, extraer contexto de la DB
        contexto_db = cleaned_data.get("contexto_db", {})
        client_info = {}
        
        # Mapear campos importantes de contexto_db a client_info
        if contexto_db:
            # Información básica
            if contexto_db.get("nombre"):
                client_info["nombre"] = contexto_db["nombre"]
            if contexto_db.get("whatsapp"):
                client_info["telefono"] = contexto_db["whatsapp"]
            if contexto_db.get("email"):
                client_info["email"] = contexto_db["email"]
            if contexto_db.get("empresa"):
                client_info["empresa"] = contexto_db["empresa"]
            if contexto_db.get("categoria_empresa"):
                client_info["categoria_empresa"] = contexto_db["categoria_empresa"]
            
            # Información de conversación previa
            if contexto_db.get("resumen_conversacion"):
                client_info["resumen_anterior"] = contexto_db["resumen_conversacion"]
            if contexto_db.get("acciones_tomadas"):
                client_info["acciones_tomadas"] = contexto_db["acciones_tomadas"]
            if contexto_db.get("acciones_por_tomar"):
                client_info["acciones_por_tomar"] = contexto_db["acciones_por_tomar"]
            
            # Información comercial
            if contexto_db.get("interes_detectado"):
                client_info["interes_detectado"] = contexto_db["interes_detectado"]
            if contexto_db.get("presupuesto"):
                client_info["presupuesto_mencionado"] = contexto_db["presupuesto"]
            if contexto_db.get("es_recurrente"):
                client_info["es_cliente_recurrente"] = contexto_db["es_recurrente"]
            if contexto_db.get("num_interacciones"):
                client_info["numero_interacciones"] = contexto_db["num_interacciones"]
            if contexto_db.get("urgencia"):
                client_info["urgencia"] = contexto_db["urgencia"]
            if contexto_db.get("sentimiento"):
                client_info["sentimiento"] = contexto_db["sentimiento"]
        
        # Guardar en estado
        TEXT_CHAT_STATE[conversation_id]["client_info"] = client_info
        
        logger.info(f"📝 Client info construido con {len(client_info)} campos: {list(client_info.keys())}")
    else:
        logger.info(f"↩️ Interacción posterior para {conversation_id}")
        client_info = None  # NO usar contexto en mensajes posteriores
    
    # ===== PASO 6: GESTIONAR HISTORIAL =====
    history = conversation_histories[conversation_id]
    
    # Limitar historial a 20 mensajes
    if len(history) > 20:
        history = history[-20:]
        conversation_histories[conversation_id] = history
    
    # Agregar mensaje del usuario
    full_conversation_histories[conversation_id].append({"role": "user", "content": current_message})
    history.append({"role": "user", "content": current_message})
    
    # ===== PASO 7: ACTUALIZAR CONTADORES =====
    state = TEXT_CHAT_STATE[conversation_id]
    state["last_activity_ts"] = time.time()
    
    if "message_count" not in state:
        state["message_count"] = {"user": 0, "assistant": 0}
        state["word_count"] = {"user": 0, "assistant": 0}
    
    state["message_count"]["user"] += 1
    state["word_count"]["user"] += len(current_message.split())
    
    # ===== PASO 8: PROCESAR CON IA =====
    try:
        response_data = await process_text_message(
            user_id=user_id,
            current_user_message=current_message,
            history=history,
            client_info=client_info  # Solo se pasa en primera interacción
        )
        
        ai_reply = response_data.get("reply_text", "No pude obtener una respuesta.")
        status = response_data.get("status", "success")
        
        logger.info(f"🤖 [AGENTE] {user_id}: '{ai_reply}'")
        
        # Log de herramientas
        tools_used = response_data.get("tools_used", [])
        if tools_used:
            logger.info(f"🔧 [HERRAMIENTAS] {user_id} usó: {', '.join(tools_used)}")
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        traceback.print_exc()
        ai_reply = "Hubo un error procesando tu mensaje. Por favor intenta de nuevo."
        status = "error"
    
    # ===== PASO 9: AGREGAR RESPUESTA AL HISTORIAL =====
    if ai_reply:
        full_conversation_histories[conversation_id].append({"role": "assistant", "content": ai_reply})
        history.append({"role": "assistant", "content": ai_reply})
        
        # Actualizar contadores de respuesta
        state["message_count"]["assistant"] += 1
        state["word_count"]["assistant"] += len(ai_reply.split())
    
    # ===== PASO 10: DETECTAR FIN DE CONVERSACIÓN =====
    end_chat = bool(response_data.get("end_chat"))
    end_reason = response_data.get("end_reason")
    
    if end_chat and not state.get("ended"):
        state["ended"] = True
        try:
            await _end_text_conversation(conversation_id, state, reason=end_reason or "assistant_requested_end")
        except Exception as e:
            logger.error(f"Error en _end_text_conversation: {e}", exc_info=True)
    
    logger.info(f"[LATENCIA] Mensaje procesado en {1000*(time.perf_counter()-t0):.1f} ms")
    
    # ===== PASO 11: RETORNAR RESPUESTA =====
    return {
        "reply_text": ai_reply,
        "status": status,
        "conversation_history": history,
        "end_chat": end_chat,
        "end_reason": end_reason
    }


# ========== APIS DE HERRAMIENTAS ==========

@app.post("/n8n/process-appointment-request")
async def n8n_process_appointment_request(
    user_query_for_date_time: str = Body(...),
    day_param: Optional[int] = Body(None),
    month_param: Optional[Union[str, int]] = Body(None),
    year_param: Optional[int] = Body(None),
    fixed_weekday_param: Optional[str] = Body(None),
    explicit_time_preference_param: Optional[str] = Body(None),
    is_urgent_param: Optional[bool] = Body(False),
    more_late_param: Optional[bool] = Body(False),
    more_early_param: Optional[bool] = Body(False)
):
    """🗓️ Procesa solicitud de cita"""
    logger.info(f"🗓️ Procesando solicitud: {user_query_for_date_time}")
    
    try:
        result = buscarslot.process_appointment_request(
            user_query_for_date_time=user_query_for_date_time,
            day_param=day_param,
            month_param=month_param,
            year_param=year_param,
            fixed_weekday_param=fixed_weekday_param,
            explicit_time_preference_param=explicit_time_preference_param,
            is_urgent_param=is_urgent_param or False,
            more_late_param=more_late_param or False,
            more_early_param=more_early_param or False
        )
        return result
    except Exception as e:
        logger.error(f"Error en appointment request: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


@app.post("/n8n/create-calendar-event")
async def n8n_create_calendar_event(
    name: str = Body(...),
    phone: str = Body(...),
    reason: str = Body(...),
    start_time: str = Body(...),
    end_time: str = Body(...)
):
    """📅 Crea evento en calendario"""
    logger.info(f"📅 Creando cita para {name}")
    
    try:
        result = create_calendar_event(
            name=name,
            phone=phone,
            reason=reason,
            start_time=start_time,
            end_time=end_time
        )
        
        if "error" in result:
            return {"status": "ERROR", "message": result["error"]}
            
        return {
            "status": "SUCCESS",
            "event_id": result.get("id"),
            "message": "Cita creada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error creando cita: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


@app.post("/n8n/edit-calendar-event")
async def n8n_edit_calendar_event(
    event_id: str = Body(...),
    new_start_time_iso: str = Body(...),
    new_end_time_iso: str = Body(...),
    new_name: Optional[str] = Body(None),
    new_reason: Optional[str] = Body(None),
    new_phone_for_description: Optional[str] = Body(None)
):
    """✏️ Edita evento existente"""
    logger.info(f"✏️ Editando evento {event_id}")
    
    try:
        result = edit_calendar_event(
            event_id=event_id,
            new_start_time_iso=new_start_time_iso,
            new_end_time_iso=new_end_time_iso,
            new_name=new_name,
            new_reason=new_reason,
            new_phone_for_description=new_phone_for_description
        )
        
        if "error" in result:
            return {"status": "ERROR", "message": result["error"]}
            
        return {
            "status": "SUCCESS",
            "message": "Cita modificada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error editando cita: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


@app.post("/n8n/delete-calendar-event")
async def n8n_delete_calendar_event(
    event_id: str = Body(...),
    original_start_time_iso: str = Body(...)
):
    """🗑️ Elimina evento del calendario"""
    logger.info(f"🗑️ Eliminando evento {event_id}")
    
    try:
        result = delete_calendar_event(
            event_id=event_id,
            original_start_time_iso=original_start_time_iso
        )
        
        if "error" in result:
            return {"status": "ERROR", "message": result["error"]}
            
        return {
            "status": "SUCCESS",
            "message": "Cita eliminada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error eliminando cita: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


@app.post("/n8n/search-calendar-event-by-phone")
async def n8n_search_calendar_event_by_phone(phone: str = Body(...)):
    """🔍 Busca citas por teléfono"""
    logger.info(f"🔍 Buscando citas para teléfono: {phone}")
    
    try:
        search_results = search_calendar_event_by_phone(phone=phone)
        return {"search_results": search_results}
    except Exception as e:
        logger.error(f"Error buscando citas: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


@app.post("/n8n/select-calendar-event-by-index")
async def n8n_select_calendar_event_by_index(selected_index: int = Body(...)):
    """👆 Selecciona cita por índice"""
    logger.info(f"👆 Seleccionando cita índice: {selected_index}")
    
    try:
        result = select_calendar_event_by_index(selected_index=selected_index)
        
        if "error" in result:
            return {"status": "ERROR", "message": result["error"]}
            
        return {
            "status": "SUCCESS",
            "message": result["message"],
            "event_id": result.get("event_id")
        }
    except Exception as e:
        logger.error(f"Error seleccionando cita: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}


# ========== ENDPOINTS DE ADMINISTRACIÓN ==========

@app.get("/admin/call-status")
async def get_call_status():
    """
    📊 Obtiene el estado de las llamadas activas
    
    Útil para debugging y monitoreo
    """
    t0 = time.perf_counter()
    # TODO: Implementar tracking de llamadas activas
    logger.info(f"[LATENCIA] Admin call-status consultado en {1000*(time.perf_counter()-t0):.1f} ms")
    return {
        "active_calls": 0,
        "message": "Endpoint en desarrollo"
    }


@app.get("/admin/rate-limit-status")
async def get_rate_limit_status():
    """
    📊 Obtiene el estado del rate limiting global
    
    Útil para monitorear el uso de llamadas diarias
    """
    t0 = time.perf_counter()
    current_time = time.time()
    
    # Calcular tiempo restante hasta el reset
    time_until_reset = 0
    if global_call_limiter["last_reset"]:
        time_since_reset = current_time - global_call_limiter["last_reset"]
        time_until_reset = max(0, 86400 - time_since_reset)
    
    # Calcular porcentaje de uso
    usage_percentage = (global_call_limiter["count"] / 15) * 100 if global_call_limiter["count"] > 0 else 0
    
    status_info = {
        "calls_today": global_call_limiter["count"],
        "max_calls_per_day": 15,
        "remaining_calls": 15 - global_call_limiter["count"],
        "usage_percentage": round(usage_percentage, 1),
        "time_until_reset_seconds": int(time_until_reset),
        "time_until_reset_hours": round(time_until_reset / 3600, 1),
        "last_reset_timestamp": global_call_limiter["last_reset"],
        "first_call_today": global_call_limiter["first_call"],
        "limit_type": "global_daily"
    }
    
    logger.info(f"[LATENCIA] Admin rate-limit-status consultado en {1000*(time.perf_counter()-t0):.1f} ms")
    return status_info


@app.post("/admin/reload-cache")
async def reload_cache():
    """
    🔄 Recarga los datos en caché
    
    Útil cuando se actualizan horarios o información
    """
    t0 = time.perf_counter()
    try:
        buscarslot.load_free_slots_to_cache()
        
        logger.info(f"[LATENCIA] Admin reload-cache completado en {1000*(time.perf_counter()-t0):.1f} ms")
        return {
            "status": "SUCCESS",
            "message": "Caché recargado exitosamente"
        }
    except Exception as e:
        logger.error(f"Error recargando caché: {e}")
        return {
            "status": "ERROR",
            "message": str(e)
        }


@app.get("/admin/health-check")
async def health_check():
    """
    🏥 Endpoint detallado de salud
    
    Verifica el estado de todos los componentes
    """
    t0 = time.perf_counter()
    health_status = {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "cache": "unknown",
            "integrations": "unknown"
        }
    }
    
    # Verificar caché
    try:
        # No hay caché de datos de consultorio, solo slots de calendario
        health_status["components"]["cache"] = "healthy" 
    except Exception as e:
        health_status["components"]["cache"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    logger.info(f"[LATENCIA] Admin health-check completado en {1000*(time.perf_counter()-t0):.1f} ms")
    return health_status


# =================== UTILIDADES PARA CHATS DE TEXTO ===================

async def _background_text_chat_monitor() -> None:
    """
    Monitorea inactividad de chats de texto y ejecuta:
    - Pulse a los 20 minutos sin actividad
    - Cierre a los 60 minutos sin actividad
    """
    PULSE_AFTER_SECONDS = 20 * 60
    CLOSE_AFTER_SECONDS = 60 * 60
    CHECK_INTERVAL = 60

    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            now = time.time()
            for conversation_id in list(TEXT_CHAT_STATE.keys()):
                state = TEXT_CHAT_STATE.get(conversation_id) or {}
                if state.get("ended"):
                    continue
                last_ts = state.get("last_activity_ts")
                if not last_ts:
                    continue
                idle = now - last_ts
                if idle >= PULSE_AFTER_SECONDS and not state.get("pulse_sent"):
                    try:
                        logger.info(f"⏰ [PULSE] Mensaje de pulse enviado a {conversation_id} después de 20min de inactividad")
                        await _send_text_pulse(conversation_id, state)
                        state["pulse_sent"] = True
                    except Exception as e:
                        logger.error(f"Error enviando pulse: {e}")
                if idle >= CLOSE_AFTER_SECONDS:
                    state["ended"] = True
                    try:
                        logger.info(f"🔚 [SESIÓN] Sesión terminada tras 60 min de inactividad de {conversation_id}")
                        await _end_text_conversation(conversation_id, state, reason="timeout_inactivity")
                    except Exception as e:
                        logger.error(f"Error cerrando conversación por timeout: {e}")
        except asyncio.CancelledError:
            logger.info("Monitor de chats de texto cancelado")
            break
        except Exception as e:
            logger.error(f"Error en monitor de chats de texto: {e}")


async def _send_text_pulse(conversation_id: str, state: Dict[str, Any]) -> None:
    """
    Envía un 'pulse' como mensaje adicional en la conversación existente.
    Simplemente añade el mensaje al historial como si fuera una respuesta automática del asistente.
    """
    message = "Por aquí sigo si necesitas algo 😊"
    
    # Añadir el pulse al historial de la conversación
    if conversation_id in conversation_histories:
        pulse_message = {"role": "assistant", "content": message}
        # Agregar a historial completo
        full_conversation_histories[conversation_id].append(pulse_message)
        # Agregar a historial recortado
        conversation_histories[conversation_id].append(pulse_message)
        logger.info(f"Pulse añadido al historial de {conversation_id}: '{message}'")
    else:
        logger.warning(f"No se encontró historial para {conversation_id}")


async def _end_text_conversation(conversation_id: str, state: Dict[str, Any], reason: str) -> None:
    """
    Envía a n8n el resumen completo de la conversación con TODA la metadata.
    """
    # Agregar mensaje final
    if conversation_id in conversation_histories:
        final_message = "Ahora cerraré nuestra sesión. ¡Gracias! 😊"
        final_message_obj = {"role": "assistant", "content": final_message}
        
        full_conversation_histories[conversation_id].append(final_message_obj)
        conversation_histories[conversation_id].append(final_message_obj)
        
        logger.info(f"💬 [MENSAJE FINAL] {conversation_id}: '{final_message}'")
    
    url = "https://n8n.aissistantpros.tech/webhook/conversation/end"
    history = full_conversation_histories.get(conversation_id, [])
    
    # Calcular timestamps y duración
    first_ts = state.get("first_message_ts", time.time())
    last_ts = state.get("last_activity_ts", time.time())
    duration_seconds = int(last_ts - first_ts)
    duration_minutes = round(duration_seconds / 60, 2)
    
    # Extraer metadata del user_profile
    metadata = state.get("metadata", {})
    plataforma_info = state.get("plataforma_info", {})
    
    # Preparar payload COMPLETO con toda la metadata
    payload = {
        # Identificadores
        "conversation_id": conversation_id,
        "canal": state.get("canal"),
        
        # Información del usuario (desde user_profile)
        "telefono": metadata.get("telefono"),
        "nombre": metadata.get("nombre_completo"),
        "email": metadata.get("email"),
        "user_id_canal": metadata.get("user_id_canal"),
        
        # IDs específicos de cada canal (desde user_profile.ids_canales)
        "facebook_id": metadata.get("ids_canales", {}).get("facebook"),
        "whatsapp_id": metadata.get("ids_canales", {}).get("whatsapp"),
        "instagram_id": metadata.get("ids_canales", {}).get("instagram"),
        
        # Información de plataforma (desde plataforma_info)
        "os": plataforma_info.get("sistema_operativo"),
        "browser": plataforma_info.get("navegador"),
        "plataforma": plataforma_info.get("plataforma"),
        "timezone": plataforma_info.get("timezone"),
        "language": plataforma_info.get("language"),
        
        # Origen y contexto
        "source_url": state.get("origen_url"),
        "timestamp_inicio": state.get("timestamp_inicio"),
        
        # Historial completo de la conversación
        "history": history,
        
        # Timestamps y duración
        "fecha_inicio": datetime.fromtimestamp(first_ts).isoformat(),
        "fecha_fin": datetime.fromtimestamp(last_ts).isoformat(),
        "duracion_segundos": duration_seconds,
        "duracion_minutos": duration_minutes,
        
        # Métricas de la conversación
        "message_count": state.get("message_count", {}),
        "word_count": state.get("word_count", {}),
        
        # Razón de cierre
        "end_reason": reason
    }
    
    logger.info(f"📤 Enviando resumen completo de {conversation_id} a n8n")
    logger.info(f"   └─ Mensajes: {len(history)}, Duración: {duration_minutes} min, Canal: {state.get('canal')}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 300:
                logger.error(f"End webhook status {resp.status_code}: {resp.text[:200]}")
            else:
                logger.info(f"✅ Resumen completo enviado a n8n para {conversation_id}")
    except Exception as e:
        logger.error(f"Error enviando resumen a n8n: {e}")
    
    # Limpiar estado local
    TEXT_CHAT_STATE.pop(conversation_id, None)
    conversation_histories.pop(conversation_id, None)
    full_conversation_histories.pop(conversation_id, None)
    
    logger.info(f"🧹 Estado local limpiado para {conversation_id}")


# ========== MANEJO DE ERRORES GLOBAL ==========

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    🚨 Manejador global de excepciones
    """
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    
    return {
        "status": "ERROR",
        "message": "Error interno del servidor",
        "detail": str(exc) if os.getenv("DEBUG") == "true" else None
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )