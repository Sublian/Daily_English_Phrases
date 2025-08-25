import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    """Configuración de la aplicación"""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'tu-clave-secreta-aqui')
    
    # Configuración de base de datos
    DB_CONFIG = {
        'user': os.getenv("DB_USER"),
        'password': os.getenv("DB_PASSWORD"),
        'host': os.getenv("DB_HOST"),
        'database': os.getenv("DB_NAME"),
        'charset': 'utf8mb4',
        'autocommit': True
    }
    
    # Zona horaria local
    LOCAL_TZ = timezone(timedelta(hours=-5))
    
    # Debug mode
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Configuración de email
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    
    # Email del administrador para notificaciones
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', EMAIL_USER)  # Por defecto usa el mismo email del sistema