import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling
import logging
from typing import Optional, Dict, Any
import time
from contextlib import contextmanager

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(funcName)s:%(lineno)d] %(message)s",
    handlers=[
        logging.FileHandler("/home/subliandev/mysite/logs/envio_frases.log", encoding='utf-8'),
        logging.StreamHandler()  # También muestra en consola
    ]
)

logger = logging.getLogger(__name__)

# Carga variables de entorno
load_dotenv()

# Configuración de base de datos
DB_CONFIG = {
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True,
    'pool_name': 'frases_pool',
    'pool_size': 5,
    'pool_reset_session': True
}

# Configuración de email
EMAIL_CONFIG = {
    'user': os.getenv("EMAIL_USER"),
    'password': os.getenv("EMAIL_PASS"),
    'destinatario': os.getenv("EMAIL_DESTINATARIO"),
    'smtp_server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    'smtp_port': int(os.getenv("SMTP_PORT", "587"))
}

# Zona horaria local (UTC-5)
LOCAL_TZ = timezone(timedelta(hours=-5))

class DatabaseManager:
    """Gestor de conexiones a la base de datos con pool de conexiones"""

    def __init__(self):
        try:
            self.pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
            logger.info("Pool de conexiones creado exitosamente")
        except mysql.connector.Error as err:
            logger.critical(f"Error creando pool de conexiones: {err}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager para manejo seguro de conexiones"""
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
        except mysql.connector.Error as err:
            logger.error(f"Error de conexión a la base de datos: {err}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

class FraseService:
    """Servicio para operaciones relacionadas con frases"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def obtener_frase_dia(self, fecha: datetime = None) -> Optional[Dict[str, Any]]:
        """Obtiene la frase del día basada en el día del año"""
        if fecha is None:
            fecha = datetime.now(LOCAL_TZ)

        dia_del_ano = fecha.timetuple().tm_yday
        logger.info(f"Buscando frase para el día {dia_del_ano} del año")

        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM frases_dia WHERE dia_del_ano = %s",
                    (dia_del_ano,)
                )
                frase = cursor.fetchone()

                if frase:
                    logger.info(f"Frase encontrada: ID {frase['id']}")
                else:
                    logger.warning(f"No se encontró frase para el día {dia_del_ano}")

                return frase

    def registrar_envio(self, frase_id: int, destinatario: str,
                       resultado: str, descripcion_error: str = None):
        """Registra el resultado del envío en la base de datos"""
        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trazabilidad_envio
                    (frase_id, destinatario, resultado, descripcion_error)
                    VALUES (%s, %s, %s, %s)
                """, (frase_id, destinatario, resultado, descripcion_error))

                logger.info(f"Envío registrado: frase_id={frase_id}, resultado={resultado}")

class EmailService:
    """Servicio para envío de correos electrónicos"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validar_configuracion()

    def _validar_configuracion(self):
        """Valida que la configuración de email esté completa"""
        required_keys = ['user', 'password', 'destinatario']
        for key in required_keys:
            if not self.config.get(key):
                raise ValueError(f"Configuración de email incompleta: falta {key}")

    def crear_mensaje(self, frase_data: Dict[str, Any]) -> MIMEMultipart:
        """Crea el mensaje de correo con formato mejorado"""
        msg = MIMEMultipart('alternative')

        # Headers del mensaje
        msg['Subject'] = "📩 Frase del Día - Inspiración Diaria"
        msg['From'] = self.config['user']
        msg['To'] = self.config['destinatario']
        msg['X-Priority'] = '3'

        # Contenido en texto plano
        texto_plano = f"""
Hola,

Aquí tienes tu frase inspiradora del día:

📌 FRASE: {frase_data.get('frase', 'N/A')}

🧠 SIGNIFICADO: {frase_data.get('significado', 'N/A')}

🗣️ EJEMPLO DE USO: {frase_data.get('ejemplo', 'N/A')}

¡Que tengas un día lleno de aprendizaje y crecimiento!

────────────────────────────────
📅 Enviado el: {datetime.now(LOCAL_TZ).strftime('%d/%m/%Y a las %H:%M')}
🤖 Sistema automático de frases diarias
        """.strip()

        # Contenido en HTML (opcional, para mejor presentación)
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #2c5aa0;">📩 Frase del Día</h2>

              <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #495057; margin-top: 0;">📌 Frase:</h3>
                <p style="font-size: 18px; font-style: italic; color: #212529;">
                  "{frase_data.get('frase', 'N/A')}"
                </p>

                <h3 style="color: #495057;">🧠 Significado:</h3>
                <p>{frase_data.get('significado', 'N/A')}</p>

                <h3 style="color: #495057;">🗣️ Ejemplo de uso:</h3>
                <p><em>{frase_data.get('ejemplo', 'N/A')}</em></p>
              </div>

              <p style="color: #6c757d; font-size: 14px; border-top: 1px solid #dee2e6; padding-top: 15px;">
                📅 Enviado el: {datetime.now(LOCAL_TZ).strftime('%d/%m/%Y a las %H:%M')}<br>
                🤖 Sistema automático de frases diarias
              </p>
            </div>
          </body>
        </html>
        """

        # Adjuntar ambas versiones
        msg.attach(MIMEText(texto_plano, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        return msg

    def enviar_correo(self, frase_data: Dict[str, Any]) -> bool:
        """Envía el correo electrónico con reintentos"""
        max_intentos = 3

        for intento in range(1, max_intentos + 1):
            try:
                logger.info(f"Intento {intento} de envío de correo")

                msg = self.crear_mensaje(frase_data)

                with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                    server.starttls()
                    server.login(self.config['user'], self.config['password'])
                    server.send_message(msg)

                logger.info("Correo enviado exitosamente")
                return True

            except smtplib.SMTPException as e:
                logger.error(f"Error SMTP en intento {intento}: {e}")
                if intento < max_intentos:
                    tiempo_espera = intento * 2  # Backoff exponencial
                    logger.info(f"Reintentando en {tiempo_espera} segundos...")
                    time.sleep(tiempo_espera)
            except Exception as e:
                logger.error(f"Error inesperado en intento {intento}: {e}")
                if intento < max_intentos:
                    time.sleep(intento * 2)

        logger.error("Falló el envío de correo después de todos los intentos")
        return False

def main():
    """Función principal del script"""
    logger.info("=" * 50)
    logger.info("INICIANDO PROCESO DE ENVÍO DE FRASE DIARIA")
    logger.info("=" * 50)

    try:
        # Verificar configuración antes de iniciar
        if not all([EMAIL_CONFIG.get('user'), EMAIL_CONFIG.get('password'), EMAIL_CONFIG.get('destinatario')]):
            logger.error("❌ Configuración de email incompleta")
            return

        # Inicializar servicios
        db_manager = DatabaseManager()
        frase_service = FraseService(db_manager)
        email_service = EmailService(EMAIL_CONFIG)

        # Obtener frase del día
        frase_data = frase_service.obtener_frase_dia()

        if not frase_data:
            logger.warning("No se encontró frase para hoy. Terminando proceso.")
            return

        # Enviar correo
        logger.info(f"Enviando frase: '{frase_data['frase'][:50]}...'")

        if email_service.enviar_correo(frase_data):
            # Registrar éxito
            frase_service.registrar_envio(
                frase_data['id'],
                EMAIL_CONFIG['destinatario'],
                'exito'
            )
            logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
        else:
            # Registrar error
            frase_service.registrar_envio(
                frase_data['id'],
                EMAIL_CONFIG['destinatario'],
                'error',
                'Error en el envío del correo después de múltiples intentos'
            )
            logger.error("❌ PROCESO FALLÓ EN EL ENVÍO")

    except Exception as e:
        logger.critical(f"💥 ERROR CRÍTICO EN MAIN: {e}", exc_info=True)

    finally:
        logger.info("=" * 50)
        logger.info("PROCESO FINALIZADO")
        logger.info("=" * 50)

if __name__ == "__main__":
    main()