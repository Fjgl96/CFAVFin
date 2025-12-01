# utils/logger.py
"""
Sistema de logging compatible con Streamlit Cloud y desarrollo local.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# ========================================
# DETECCIÓN DE ENTORNO
# ========================================

def is_streamlit_cloud():
    """Detecta si la app está corriendo en Streamlit Cloud."""
    import os
    # Streamlit Cloud tiene estas variables de entorno o paths
    return (
        os.getenv('STREAMLIT_SHARING_MODE') or 
        os.path.exists('/mount/src') or
        os.getenv('HOME', '').startswith('/home/appuser')
    )

# ========================================
# CONFIGURACIÓN DE LOGS
# ========================================

# En Streamlit Cloud, los logs solo van a console (stderr)
# Streamlit Cloud captura automáticamente los logs de console
USE_FILE_LOGGING = not is_streamlit_cloud()

if USE_FILE_LOGGING:
    # Desarrollo local - escribir a archivo
    try:
        LOGS_DIR = Path("/mnt/user-data/shared/logs")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback a directorio local
        LOGS_DIR = Path("./logs")
        try:
            LOGS_DIR.mkdir(exist_ok=True)
        except:
            USE_FILE_LOGGING = False

# Formato de logs
LOG_FORMAT = '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ========================================
# FUNCIÓN PRINCIPAL
# ========================================

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Obtiene un logger configurado.
    
    Args:
        name: Nombre del logger (ej: 'streamlit', 'agents', 'tools')
        level: Nivel de logging (default: INFO)
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # Handler para console (siempre)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo (solo en desarrollo local)
    if USE_FILE_LOGGING:
        try:
            log_filename = LOGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Si falla el file handler, seguir con console solamente
            logger.warning(f"No se pudo crear file handler: {e}")
    
    # No propagar al root logger
    logger.propagate = False
    
    return logger

# ========================================
# FUNCIÓN AUXILIAR PARA EVENTOS
# ========================================

def log_system_event(event_type: str, details: dict, logger_name: str = 'system'):
    """
    Registra un evento del sistema.
    
    Args:
        event_type: Tipo de evento (ej: 'query', 'error', 'calculation')
        details: Detalles del evento como dict
        logger_name: Nombre del logger a usar
    """
    logger = get_logger(logger_name)
    
    # Formatear mensaje
    details_str = " | ".join([f"{k}={v}" for k, v in details.items()])
    message = f"[{event_type.upper()}] {details_str}"
    
    # Log según tipo
    if event_type.lower() in ['error', 'exception']:
        logger.error(message)
    elif event_type.lower() == 'warning':
        logger.warning(message)
    else:
        logger.info(message)

# ========================================
# INFO AL IMPORTAR
# ========================================

if __name__ != "__main__":
    env = "Streamlit Cloud" if is_streamlit_cloud() else "Local"
    file_logging = "habilitado" if USE_FILE_LOGGING else "deshabilitado"
    print(f"✅ Logger inicializado | Entorno: {env} | File logging: {file_logging}")