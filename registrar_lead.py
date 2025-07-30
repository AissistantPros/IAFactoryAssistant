# registrar_lead.py
# -*- coding: utf-8 -*-
"""
Contiene la herramienta (skill) para registrar un nuevo lead en Google Sheets.
"""
import gspread
from google.oauth2.service_account import Credentials
import logging
import os
import json
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# --- Configuración de Google Sheets ---
# El nombre de la hoja de cálculo donde se guardarán los leads.
# ¡Asegúrate de que esta hoja exista en tu Google Drive!
SHEET_NAME = "Leads IA Factory"

# Define el alcance (permissions) que necesitará nuestra cuenta de servicio.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

def get_google_credentials():
    """
    Carga las credenciales de Google desde una variable de entorno.
    
    Render (y otros servicios de hosting) permiten guardar variables de entorno
    secretas. Guardaremos el contenido del JSON de credenciales en una variable
    llamada 'GOOGLE_CREDENTIALS_JSON'.
    """
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json_str:
        logger.error("La variable de entorno 'GOOGLE_CREDENTIALS_JSON' no está configurada.")
        return None
    
    try:
        creds_info = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return credentials
    except Exception as e:
        logger.error(f"Error al cargar las credenciales de Google: {e}")
        return None

def registrar_lead(nombre: str, empresa: str, telefono: str) -> dict:
    """
    Registra la información de un nuevo lead en una hoja de cálculo de Google.

    Args:
        nombre: El nombre del cliente potencial.
        empresa: El nombre de la empresa del cliente potencial.
        telefono: El número de teléfono del cliente potencial.

    Returns:
        Un diccionario indicando el resultado de la operación.
    """
    logger.info(f"Iniciando el proceso para registrar al lead: {nombre} de {empresa}")

    credentials = get_google_credentials()
    if not credentials:
        # Si no hay credenciales, la función devuelve un error que el LLM puede interpretar.
        return {
            "status": "error",
            "message": "Error interno de configuración. No se pudo autenticar con Google."
        }

    try:
        # Autenticar y abrir el cliente de gspread
        gc = gspread.authorize(credentials)
        
        # Abrir la hoja de cálculo por su nombre y seleccionar la primera hoja
        spreadsheet = gc.open(SHEET_NAME)
        sheet = spreadsheet.sheet1
        
        # Crear la fila de datos a insertar
        # Se incluye una marca de tiempo para saber cuándo se registró el lead.
        cancun_tz = pytz.timezone("America/Cancun")
        timestamp = datetime.now(cancun_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        row = [timestamp, nombre, empresa, telefono, "Nuevo"] # Añadimos un estado inicial
        
        # Añadir la fila a la hoja de cálculo
        sheet.append_row(row)
        
        logger.info(f"Lead '{nombre}' registrado exitosamente en la hoja '{SHEET_NAME}'.")
        
        return {
            "status": "success",
            "message": f"He registrado tus datos, {nombre}. Un especialista de {empresa} se pondrá en contacto contigo pronto."
        }

    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"ERROR: La hoja de cálculo '{SHEET_NAME}' no fue encontrada. Revisa el nombre y los permisos.")
        return {
            "status": "error",
            "message": "Error interno: No se pudo encontrar la base de datos de leads."
        }
    except Exception as e:
        logger.error(f"Ocurrió un error inesperado al interactuar con Google Sheets: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "Hubo un problema al intentar guardar tus datos. Por favor, inténtalo de nuevo más tarde."
        }

# Ejemplo de cómo se usaría (para pruebas locales si tienes el JSON):
# if __name__ == '__main__':
#     # Para probar, necesitarías tener un archivo 'credentials.json'
#     # y configurar la variable de entorno antes de ejecutar.
#     # Por ejemplo:
#     # with open('path/to/your/credentials.json', 'r') as f:
#     #     os.environ['GOOGLE_CREDENTIALS_JSON'] = f.read()
#     
#     resultado = registrar_lead("Esteban Reyna (Prueba)", "IA Factory", "9982137477")
#     print(resultado)
