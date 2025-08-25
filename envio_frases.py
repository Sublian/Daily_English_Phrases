import os
import logging
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# Importar nuestros módulos
from config import Config
from database import DatabaseManager
from frase_service import FraseService
from user_service import UserService
from email_service import EmailService

# Cargar variables de entorno
load_dotenv()

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

# Configuración de email desde variables de entorno
EMAIL_CONFIG = {
    'user': os.getenv("EMAIL_USER"),
    'password': os.getenv("EMAIL_PASS"),
    'smtp_server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    'smtp_port': int(os.getenv("SMTP_PORT", "587"))
}

class FraseDiariaManager:
    """Gestor principal del sistema de frases diarias"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.frase_service = FraseService(self.db_manager)
        self.user_service = UserService(self.db_manager)
        self.email_service = EmailService(EMAIL_CONFIG)

    def validar_configuracion(self) -> bool:
        """Valida que toda la configuración esté correcta"""
        required_env = ['EMAIL_USER', 'EMAIL_PASS', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME']

        missing = [var for var in required_env if not os.getenv(var)]
        if missing:
            logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
            return False

        logger.info("✅ Configuración validada correctamente")
        return True

    def procesar_envios(self) -> Dict[str, Any]:
        """Procesa todos los envíos del día"""
        # Obtener frase del día
        frase_data = self.frase_service.obtener_frase_dia()
        if not frase_data:
            logger.warning("⚠️ No se encontró frase para hoy. Terminando proceso.")
            return {'success': False, 'error': 'No hay frase para hoy'}

        # Obtener usuarios activos
        usuarios_activos = self.user_service.get_active_users()
        if not usuarios_activos:
            logger.warning("⚠️ No hay usuarios activos para enviar emails.")
            return {'success': False, 'error': 'No hay usuarios activos'}

        logger.info(f"📧 Iniciando envío masivo de frase: '{frase_data['frase'][:50]}...'")
        logger.info(f"👥 Total de usuarios activos: {len(usuarios_activos)}")

        # Procesar envíos
        usuarios_exitosos = []
        usuarios_fallidos = []

        for i, usuario in enumerate(usuarios_activos, 1):
            tipo_suscripcion = usuario.get('tipo_suscripcion', 'gratuito')
            nombre = usuario.get('nombre') or 'Usuario'

            logger.info(f"📤 [{i}/{len(usuarios_activos)}] Enviando a {usuario['email']} "
                       f"({nombre}, {tipo_suscripcion.title()})")

            if self.email_service.enviar_correo(frase_data, usuario):
                usuarios_exitosos.append(usuario)
                # Registrar envío exitoso
                self.frase_service.registrar_envio(frase_data['id'], usuario['id'], 'exito')
            else:
                usuarios_fallidos.append({
                    'usuario': usuario,
                    'error': 'Error en el envío después de múltiples intentos'
                })
                # Registrar envío fallido
                self.frase_service.registrar_envio(
                    frase_data['id'],
                    usuario['id'],
                    'error',
                    'Error en el envío después de múltiples intentos'
                )

        # Resumen de resultados
        resultados = {
            'success': True,
            'frase_id': frase_data['id'],
            'total_usuarios': len(usuarios_activos),
            'exitosos': len(usuarios_exitosos),
            'fallidos': len(usuarios_fallidos),
            'tasa_exito': round((len(usuarios_exitosos) / len(usuarios_activos) * 100), 2),
            'usuarios_exitosos': usuarios_exitosos,
            'usuarios_fallidos': usuarios_fallidos,
            'frase': frase_data['frase'][:100]
        }

        return resultados

    def generar_reporte(self, resultados: Dict[str, Any]) -> None:
        """Genera reporte detallado del proceso"""
        logger.info("=" * 60)
        logger.info("📊 REPORTE FINAL DEL ENVÍO")
        logger.info("=" * 60)

        if not resultados.get('success'):
            logger.error(f"❌ PROCESO FALLÓ: {resultados.get('error', 'Error desconocido')}")
            return

        logger.info(f"📝 Frase enviada: '{resultados['frase']}...'")
        logger.info(f"👥 Total usuarios: {resultados['total_usuarios']}")
        logger.info(f"✅ Envíos exitosos: {resultados['exitosos']}")
        logger.info(f"❌ Envíos fallidos: {resultados['fallidos']}")
        logger.info(f"📈 Tasa de éxito: {resultados['tasa_exito']}%")

        # Detalles por tipo de suscripción
        usuarios_exitosos = resultados['usuarios_exitosos']
        premium_exitosos = [u for u in usuarios_exitosos if u.get('tipo_suscripcion', '').lower() == 'premium']
        gratuitos_exitosos = [u for u in usuarios_exitosos if u.get('tipo_suscripcion', '').lower() == 'gratuito']

        logger.info(f"💎 Usuarios Premium exitosos: {len(premium_exitosos)}")
        logger.info(f"📧 Usuarios Gratuitos exitosos: {len(gratuitos_exitosos)}")

        # Mostrar usuarios fallidos si los hay
        if resultados['usuarios_fallidos']:
            logger.warning("⚠️ USUARIOS CON ERRORES:")
            for user_error in resultados['usuarios_fallidos']:
                usuario = user_error['usuario']
                error = user_error['error']
                logger.warning(f"   - {usuario['email']} ({usuario.get('nombre', 'Sin nombre')}): {error}")

        # Estadísticas adicionales
        stats = self.frase_service.get_estadisticas_envios()
        logger.info(f"📊 Estadísticas del día:")
        logger.info(f"   - Total envíos hoy: {stats['total_hoy']}")
        logger.info(f"   - Exitosos hoy: {stats['exitosos_hoy']}")
        logger.info(f"   - Tasa éxito hoy: {stats['tasa_exito_hoy']}%")

        logger.info("=" * 60)


def main():
    """Función principal del script"""
    logger.info("🚀 " + "=" * 50)
    logger.info("🚀 INICIANDO SISTEMA DE FRASES DIARIAS")
    logger.info("🚀 " + "=" * 50)

    try:
        # Inicializar manager
        manager = FraseDiariaManager()

        # Validar configuración
        if not manager.validar_configuracion():
            logger.error("❌ Configuración inválida. Terminando proceso.")
            return

        # Procesar envíos
        logger.info("📧 Iniciando proceso de envíos...")
        resultados = manager.procesar_envios()

        # Generar reporte
        manager.generar_reporte(resultados)

        # Mensaje final
        if resultados.get('success'):
            if resultados['exitosos'] == resultados['total_usuarios']:
                logger.info("🎉 ¡PROCESO COMPLETADO PERFECTAMENTE! Todos los envíos fueron exitosos.")
            elif resultados['exitosos'] > 0:
                logger.info(f"✅ PROCESO COMPLETADO PARCIALMENTE. {resultados['exitosos']}/{resultados['total_usuarios']} envíos exitosos.")
            else:
                logger.error("💥 PROCESO FALLÓ COMPLETAMENTE. No se pudo enviar a ningún usuario.")
        else:
            logger.error("💥 PROCESO FALLÓ. Ver detalles arriba.")

    except Exception as e:
        logger.critical(f"💥 ERROR CRÍTICO EN MAIN: {e}", exc_info=True)

    finally:
        logger.info("🏁 " + "=" * 50)
        logger.info("🏁 PROCESO FINALIZADO")
        logger.info("🏁 " + "=" * 50)


if __name__ == "__main__":
    main()