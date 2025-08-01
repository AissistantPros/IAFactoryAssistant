# synthetic_responses.py
# -*- coding: utf-8 -*-
"""
Módulo de respuestas sintéticas para evitar segundo round al LLM
"""
import random
import logging
from typing import Dict, Any, List
from utils import convertir_hora_a_palabras, format_date_nicely
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# Plantillas de respuestas por herramienta y status
TEMPLATES = {
    "process_appointment_request": {
        "SLOT_LIST": [
            "Para el {pretty_date}, tengo disponible: {available_pretty}. ¿Alguna de estas horas le funciona?",
            "Le encontré espacio el {pretty_date} a las: {available_pretty}. ¿Le acomoda alguna?",
            "Perfecto, para {pretty_date} hay lugar a las: {available_pretty}. ¿Le sirve alguna de estas horas?",
            "Tengo estos horarios para el {pretty_date}: {available_pretty}. ¿Le conviene algun horario?",
            "El {pretty_date} puedo ofrecerle: {available_pretty}. ¿Qué hora le queda mejor?"
        ],
        "SLOT_FOUND_LATER": [
            "Busqué para el {requested_date_iso} y no había espacio. El siguiente disponible es el {suggested_date_iso}. ¿Le parece bien?",
            "No hay lugar el día solicitado. Tengo disponible el {suggested_date_iso} a las {available_pretty}. ¿Lo tomamos?",
            "La fecha que pidió está llena. ¿Le funciona el {suggested_date_iso}? Tengo: {available_pretty}. ¿Le acomoda?",
            "No encontré espacio para entonces. El próximo hueco es el {suggested_date_iso}: {available_pretty}. ¿Está bien?",
            "Esa fecha no tiene disponibilidad. Puedo ofrecerle el {suggested_date_iso} en estos horarios: {available_pretty}. ¿Le sirve alguno?"
        ],
        "NO_SLOT": [
            "Lo siento, no encontré horarios disponibles en los próximos meses.",
            "Disculpe, no hay espacios libres para las fechas consultadas.",
            "No tengo disponibilidad en el período solicitado. ¿Desea que busque más adelante?",
            "Lamentablemente no hay citas disponibles por ahora.",
            "La agenda está completa para esas fechas. ¿Probamos con otro período?"
        ],
        "NO_MORE_LATE": [
            "No hay horarios más tarde ese día. ¿Quiere que busque en otro día?",
            "Ya no quedan espacios más tarde. ¿Revisamos otra fecha?",
            "Ese fue el último horario del día. ¿Buscamos en otra fecha?",
            "No tengo nada más tarde ese día. ¿Qué tal otro día?"
        ],
        "NO_MORE_EARLY": [
            "No hay horarios más temprano ese día. ¿Quiere que busque en otro día?",
            "No tengo espacios más temprano. ¿Probamos otra fecha?",
            "Ese es el primer horario disponible del día. ¿Busco en otra fecha?",
            "No hay nada más temprano ese día. ¿Revisamos otro día?"
        ],
        "NEED_EXACT_DATE": [
            "¿Podría indicarme la fecha con mayor precisión?",
            "Necesito que me especifique mejor la fecha que desea.",
            "¿Me puede dar una fecha más específica por favor?",
            "Para buscar disponibilidad necesito una fecha exacta. ¿Cuál prefiere?",
            "¿Qué fecha exacta le gustaría consultar?"
        ],
        "OUT_OF_RANGE": [
            "Atendemos de nueve treinta a dos de la tarde. ¿Busco dentro de ese rango?",
            "El horario de consulta es de 9:30 AM a 2:00 PM. ¿Le busco en ese horario?",
            "Solo agendamos en horario de consulta: 9:30 a 14:00. ¿Está bien?",
            "Nuestro horario es de nueve y media a dos. ¿Busco ahí?",
            "Las consultas son de 9:30 de la mañana a 2 de la tarde. ¿Le parece?"
        ]
    },
    "create_calendar_event": {
        "success": [
            "Perfecto, su cita quedó agendada. Le puedo ayudar con algo más?",
            "Listo, ya está registrada su cita. ¿Necesita algo más?",
            "Excelente, cita confirmada. ¿Hay algo más en lo que le pueda ayudar?",
            "Su cita ha sido creada exitosamente. ¿Puedo ayudarle con algo más?",
            "Quedó guardada su cita. ¿Algo más que necesite?",
        ],
        "error": [
            "Hubo un problema al crear la cita. Permítame intentar nuevamente.",
            "No pude agendar la cita. Déjeme verificar qué sucedió.",
            "Ocurrió un error. Voy a intentar guardar su cita nuevamente.",
            "Disculpe, no se pudo crear la cita. Permítame otro momento.",
            "Hubo una falla técnica. Déjeme intentar de nuevo."
        ],
        "validation_error": [  
            "Disculpe, hubo un error con la fecha. Permítame corregirlo.",
            "Parece que hay un problema con los datos. Déjeme verificar.",
            "No pude validar la información. Permítame intentar nuevamente."
        ]
    },
    "search_calendar_event_by_phone": {
        "found": [
            "Encontré su cita para el {pretty_date}. ¿Desea modificarla o cancelarla?",
            "Tiene una cita agendada el {pretty_date}. ¿Qué desea hacer?",
            "Su cita está programada para el {pretty_date}. ¿Necesita cambiarla?",
            "Veo que tiene cita el {pretty_date}. ¿Desea hacer algún cambio?",
            "Localicé su cita del {pretty_date}. ¿Qué necesita?"
        ],
        "not_found": [
            "No encontré citas con ese número. ¿Desea agendar una nueva?",
            "No hay citas registradas con ese teléfono. ¿Quiere hacer una?",
            "No localizo citas previas. ¿Le agendo una nueva?",
            "Sin resultados para ese número. ¿Creamos una cita?",
            "No tengo citas registradas. ¿Desea agendar?"
        ],
        "multiple": [
            "Encontré varias citas con ese número. ¿Cuál necesita consultar?",
            "Hay múltiples citas registradas. ¿De cuál fecha hablamos?",
            "Tiene varias citas agendadas. ¿Cuál desea revisar?",
            "Hay más de una cita. ¿Me puede indicar la fecha?",
            "Encontré varias. ¿Qué fecha específica busca?"
        ]
    },
    "edit_calendar_event": {
        "success": [
            "Su cita ha sido modificada correctamente.",
            "Listo, cambié su cita como solicitó.",
            "Perfecto, su cita fue reprogramada.",
            "Cita actualizada exitosamente.",
            "Ya quedó el cambio de su cita."
        ],
        "error": [
            "No pude modificar la cita. ¿Intentamos de nuevo?",
            "Hubo un error al cambiar la cita. ¿Reintentamos?",
            "No se pudo actualizar. ¿Probamos otra vez?",
            "Falló la modificación. ¿Lo intentamos nuevamente?",
            "Error al cambiar la cita. ¿Otro intento?"
        ]
    },
    "delete_calendar_event": {
        "success": [
            "Su cita ha sido cancelada.",
            "Listo, cancelé su cita.",
            "Cita eliminada correctamente.",
            "Ya quedó cancelada su cita.",
            "Su cita fue cancelada exitosamente."
        ],
        "error": [
            "No pude cancelar la cita. ¿Intentamos de nuevo?",
            "Error al cancelar. ¿Reintentamos?",
            "No se pudo eliminar la cita. ¿Probamos otra vez?",
            "Falló la cancelación. ¿Lo intentamos nuevamente?",
            "Hubo un problema al cancelar. ¿Otro intento?"
        ]
    },
    "get_cancun_weather": {
        "default": [
            "El clima en Cancún está {description}, con {temperature} grados.",
            "Actualmente en Cancún: {description}, temperatura de {temperature} grados.",
            "Cancún tiene {description} y {temperature} grados ahora.",
            "Hay {description} en Cancún, con {temperature} grados.",
            "En Cancún el clima es {description}, {temperature} grados."
        ]
    },
    "read_sheet_data": {
        "default": [
            "Aquí está la información solicitada del consultorio.",
            "Esta es la información que tenemos registrada.",
            "Los datos del consultorio son los siguientes.",
            "Le comparto la información del consultorio.",
            "Aquí tiene los datos que solicitó."
        ]
    }
}


def generate_synthetic_response(tool_name: str, result: Dict[str, Any]) -> str:
    """
    Genera una respuesta sintética basada en el resultado de una herramienta.
    """
    # FIX: Si el resultado es una lista, envolverlo en un dict
    if isinstance(result, list):
        result = {"events": result}
    t0 = time.perf_counter()
    logger.info(f"[FUNCIONALIDAD] Generando respuesta sintética para tool '{tool_name}'...")
    if tool_name not in TEMPLATES:
        return "Listo!!, está hecho. ¿Hay algo más en lo que pueda ayudarle?"
    
    # Obtener el status del resultado
    status = result.get("status", "default")
    
    # DEBUG: Agregar logging para verificar la generación
    logger.info(f"[DEBUG] Generando respuesta sintética - tool: {tool_name}, status: {status}")
    logger.info(f"[DEBUG] Templates disponibles: {list(TEMPLATES[tool_name].keys())}")
    logger.info(f"[DEBUG] Resultado completo: {result}")
    
    # Obtener las plantillas para este status
    status_templates = TEMPLATES[tool_name].get(status, TEMPLATES[tool_name].get("default", []))
    
    if not status_templates:
        # --- INICIO DE LA INTEGRACIÓN ---
        # Reemplazamos el return genérico con una lógica más inteligente.
        if "error" in result:
            return "Hubo un problema al procesar su solicitud. ¿Podemos intentar de nuevo?"
        return "Listo!!, está hecho. ¿Hay algo más en lo que pueda ayudarle?"
        # --- FIN DE LA INTEGRACIÓN ---
    
    # Seleccionar una plantilla aleatoria
    template = random.choice(status_templates)
    
    try:
        # Preparar los datos para la plantilla
        format_data = prepare_format_data(tool_name, result)
        logger.info(f"[FUNCIONALIDAD] Formateando plantilla sintética para tool '{tool_name}'...")
        
        # Formatear la plantilla con los datos
        return template.format(**format_data)
    except Exception as e:
        # logger.warning(f"Error formateando respuesta sintética: {e}")
        print(f"Advertencia: Error formateando respuesta sintética: {e}") # Usando print si no hay logger
        return template  # Devolver la plantilla sin formatear como fallback
    finally:
        logger.info(f"[LATENCIA] Respuesta sintética para tool '{tool_name}' generada en {1000*(time.perf_counter()-t0):.1f} ms")
    






def prepare_format_data(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara los datos del resultado para ser usados en las plantillas.
    """
    format_data = result.copy()
    
    # Procesar según la herramienta
    if tool_name == "process_appointment_request":
        # Convertir listas a strings
        if "available_pretty" in format_data and isinstance(format_data["available_pretty"], list):
            # Tomar máximo 3 horarios
            slots = format_data["available_pretty"][:3]
            format_data["available_pretty"] = " o ".join(slots)
        
        # Formatear fechas si vienen en ISO
        if "date_iso" in format_data:
            try:
                date_obj = datetime.fromisoformat(format_data["date_iso"])
                format_data["pretty_date"] = format_date_nicely(date_obj.date())
            except:
                format_data["pretty_date"] = format_data.get("date_iso", "la fecha")
        
        if "suggested_date_iso" in format_data:
            try:
                date_obj = datetime.fromisoformat(format_data["suggested_date_iso"])
                format_data["suggested_date_iso"] = format_date_nicely(date_obj.date())
            except:
                pass
                
        if "requested_date_iso" in format_data:
            try:
                date_obj = datetime.fromisoformat(format_data["requested_date_iso"])
                format_data["requested_date_iso"] = format_date_nicely(date_obj.date())
            except:
                pass
    
    elif tool_name == "search_calendar_event_by_phone":
        # Si hay eventos, tomar el primero para el formato
        events = result.get("events", []) or result.get("search_results", [])
        if events and len(events) > 0:
            first_event = events[0]
            # Usar el campo pretty_date si existe
            if "start_time_cancun_pretty" in first_event:
                format_data["pretty_date"] = first_event["start_time_cancun_pretty"]
            elif "date" in first_event:
                format_data["pretty_date"] = first_event["date"]
            
            format_data["count"] = len(events)
            format_data["status"] = "found" if len(events) == 1 else "multiple"
        else:
            format_data["status"] = "not_found"
    
    elif tool_name == "get_cancun_weather":
        # Extraer datos del clima
        weather_data = result.get("cancun_weather", {}).get("current", {})
        if weather_data:
            format_data["description"] = weather_data.get("description", "desconocido")
            format_data["temperature"] = weather_data.get("temperature", "N/A").replace("°C", "")
            format_data["feels_like"] = weather_data.get("feels_like", "N/A").replace("°C", "")
            format_data["humidity"] = weather_data.get("humidity", "N/A").replace("%", "")
    
    # Asegurar que error está disponible si existe
    if "error" in result and "error" not in format_data:
        format_data["error"] = result["error"]
        # Si hay error, cambiar el status para usar las plantillas de error
        if "status" not in result:
            format_data["status"] = "error"
    
    return format_data