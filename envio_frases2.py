import os
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from threading import Lock

# Importar nuestros módulos
from config import Config
from database import DatabaseManager
from frase_service import FraseService
from user_service import UserService
from email_service import EmailService

# Cargar variables de entorno
load_dotenv()

# Configuración de logging mejorada con rotación de archivos
from logging.handlers import RotatingFileHandler

log_file = "/home/subliandev/mysite/logs/envio_frases.log"
max_bytes = 10 * 1024 * 1024  # 10MB
backup_count = 5

# Crear directorio de logs si no existe
os.makedirs(os.path.dirname(log_file), exist_ok=True)

handler = RotatingFileHandler(
    log_file,
    maxBytes=max_bytes,
    backupCount=backup_count,
    encoding='utf-8'
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(funcName)s:%(lineno)d] %(message)s",
    handlers=[
        handler,
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Configuración de email desde variables de entorno con validación
EMAIL_CONFIG = {
    'user': os.getenv("EMAIL_USER"),
    'password': os.getenv("EMAIL_PASSWORD"),
    'smtp_server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    'smtp_port': int(os.getenv("SMTP_PORT", "587")),
    'max_retries': int(os.getenv("EMAIL_MAX_RETRIES", "3")),
    'batch_size': int(os.getenv("EMAIL_BATCH_SIZE", "50")),
    'max_workers': int(os.getenv("EMAIL_MAX_WORKERS", "5")),
    'retry_delay_minutes': int(os.getenv("EMAIL_RETRY_DELAY_MINUTES", "30"))
}

# Archivo para almacenar usuarios fallidos para reintentos diferidos
FAILED_USERS_FILE = "/home/subliandev/mysite/logs/failed_users.json"

class MetricsCollector:
    """Recolector de métricas para monitoreo"""

    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'total_usuarios': 0,
            'exitosos': 0,
            'fallidos': 0,
            'reintentos_diferidos': 0,
            'errores': [],
            'tiempo_total': 0,
            'tiempo_promedio_envio': [],
            'errores_red': 0,
            'otros_errores': 0
        }
        self.lock = Lock()

    def add_success(self, tiempo_envio: float):
        with self.lock:
            self.metrics['exitosos'] += 1
            self.metrics['tiempo_promedio_envio'].append(tiempo_envio)

    def add_failure(self, error: str, is_network_error: bool = False):
        with self.lock:
            self.metrics['fallidos'] += 1
            self.metrics['errores'].append(error)
            if is_network_error:
                self.metrics['errores_red'] += 1
            else:
                self.metrics['otros_errores'] += 1

    def add_deferred_retry(self):
        with self.lock:
            self.metrics['reintentos_diferidos'] += 1

    def set_total_usuarios(self, total: int):
        self.metrics['total_usuarios'] = total

    def finalizar(self):
        self.metrics['tiempo_total'] = time.time() - self.start_time
        if self.metrics['tiempo_promedio_envio']:
            self.metrics['tiempo_promedio_envio'] = sum(self.metrics['tiempo_promedio_envio']) / len(self.metrics['tiempo_promedio_envio'])
        else:
            self.metrics['tiempo_promedio_envio'] = 0
        return self.metrics

class FailedUsersManager:
    """Gestor de usuarios fallidos para reintentos diferidos"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lock = Lock()

    def save_failed_users(self, failed_users: List[Dict[str, Any]], frase_data: Dict[str, Any]):
        """Guarda usuarios fallidos con timestamp para reintentos diferidos"""
        with self.lock:
            data = {
                'timestamp': datetime.now().isoformat(),
                'frase_data': frase_data,
                'failed_users': failed_users,
                'retry_after': (datetime.now() + timedelta(minutes=EMAIL_CONFIG['retry_delay_minutes'])).isoformat()
            }

            try:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 Guardados {len(failed_users)} usuarios para reintento diferido")
            except Exception as e:
                logger.error(f"❌ Error guardando usuarios fallidos: {e}")

    def load_failed_users(self) -> Optional[Dict[str, Any]]:
        """Carga usuarios fallidos si es tiempo de reintentarlos"""
        if not os.path.exists(self.file_path):
            return None

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            retry_time = datetime.fromisoformat(data['retry_after'])
            if datetime.now() >= retry_time:
                logger.info(f"⏰ Es tiempo de reintentar envíos fallidos ({len(data['failed_users'])} usuarios)")
                return data
            else:
                time_left = retry_time - datetime.now()
                logger.info(f"⏳ Faltan {time_left.total_seconds()/60:.1f} minutos para reintento diferido")
                return None

        except Exception as e:
            logger.error(f"❌ Error cargando usuarios fallidos: {e}")
            return None

    def clear_failed_users(self):
        """Limpia el archivo de usuarios fallidos"""
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
                logger.info("🗑️ Archivo de usuarios fallidos limpiado")
        except Exception as e:
            logger.error(f"❌ Error limpiando archivo de usuarios fallidos: {e}")

class FraseDiariaManager:
    """Gestor principal del sistema de frases diarias con mejoras y reintentos diferidos"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.frase_service = FraseService(self.db_manager)
        self.user_service = UserService(self.db_manager)
        self.email_service = EmailService(EMAIL_CONFIG)
        self.metrics = MetricsCollector()
        self.failed_users_manager = FailedUsersManager(FAILED_USERS_FILE)

    @lru_cache(maxsize=1)
    def get_config(self) -> Dict[str, Any]:
        """Obtiene y cachea la configuración"""
        return {
            'max_retries': EMAIL_CONFIG['max_retries'],
            'batch_size': EMAIL_CONFIG['batch_size'],
            'max_workers': EMAIL_CONFIG['max_workers'],
            'retry_delay_minutes': EMAIL_CONFIG['retry_delay_minutes']
        }

    def validar_configuracion(self) -> bool:
        """Valida que toda la configuración esté correcta con chequeos adicionales"""
        required_env = [
            'EMAIL_USER', 'EMAIL_PASSWORD', 'DB_USER', 'DB_PASSWORD',
            'DB_HOST', 'DB_NAME', 'SMTP_SERVER', 'SMTP_PORT'
        ]

        # Validar variables requeridas
        missing = [var for var in required_env if not os.getenv(var)]
        if missing:
            logger.error(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
            return False

        # Validar valores numéricos
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            if port <= 0 or port > 65535:
                logger.error(f"❌ Puerto SMTP inválido: {port}")
                return False
        except ValueError:
            logger.error("❌ Puerto SMTP debe ser un número")
            return False

        # Validar directorio de logs
        log_dir = os.path.dirname(log_file)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except Exception as e:
                logger.error(f"❌ No se pudo crear directorio de logs: {e}")
                return False

        logger.info("✅ Configuración validada correctamente")
        return True

    def is_network_error(self, error_msg: str) -> bool:
        """Determina si un error es de red y puede beneficiarse de reintentos diferidos"""
        network_error_indicators = [
            "Network is unreachable",
            "Connection refused",
            "Connection timed out",
            "Name or service not known",
            "Temporary failure in name resolution",
            "No route to host",
            "Connection reset by peer"
        ]
        return any(indicator in error_msg for indicator in network_error_indicators)

    def procesar_usuario(self, usuario: Dict[str, Any], frase_data: Dict[str, Any],
                        is_retry: bool = False) -> Optional[Dict[str, Any]]:
        """Procesa el envío para un usuario"""
        start_time = time.time()

        try:
            if self.email_service.enviar_correo(frase_data, usuario):
                tiempo_envio = time.time() - start_time
                self.metrics.add_success(tiempo_envio)
                self.frase_service.registrar_envio(frase_data['id'], usuario['id'],
                                                 'exito_reintento' if is_retry else 'exito')
                return usuario
        except Exception as e:
            error_msg = f"Error al enviar a {usuario['email']}: {str(e)}"
            is_network_error = self.is_network_error(str(e))

            logger.error(f"❌ {error_msg} {'(Error de red)' if is_network_error else ''}")
            self.metrics.add_failure(error_msg, is_network_error)

            # Registrar en base de datos
            resultado = 'error_red' if is_network_error else 'error'
            self.frase_service.registrar_envio(frase_data['id'], usuario['id'], resultado, error_msg)

            return {'usuario': usuario, 'error': error_msg, 'is_network_error': is_network_error}

        return None

    def procesar_lote(self, usuarios: List[Dict[str, Any]], frase_data: Dict[str, Any],
                     is_retry: bool = False) -> tuple:
        """Procesa un lote de usuarios en paralelo"""
        exitosos = []
        fallidos = []

        with ThreadPoolExecutor(max_workers=self.get_config()['max_workers']) as executor:
            futures = [executor.submit(self.procesar_usuario, usuario, frase_data, is_retry)
                      for usuario in usuarios]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result and 'error' not in result:
                        exitosos.append(result)
                    elif result and 'error' in result:
                        fallidos.append(result)
                except Exception as e:
                    logger.error(f"Error en procesamiento paralelo: {e}")
                    fallidos.append({'error': str(e), 'is_network_error': False})

        return exitosos, fallidos

    def procesar_reintentos_diferidos(self) -> Dict[str, Any]:
        """Procesa reintentos diferidos de usuarios que fallaron por errores de red"""
        failed_data = self.failed_users_manager.load_failed_users()
        if not failed_data:
            return {'success': False, 'error': 'No hay reintentos pendientes'}

        frase_data = failed_data['frase_data']
        failed_users = [item['usuario'] for item in failed_data['failed_users']
                       if item.get('is_network_error', False)]

        if not failed_users:
            logger.info("📭 No hay usuarios con errores de red para reintentar")
            self.failed_users_manager.clear_failed_users()
            return {'success': False, 'error': 'No hay errores de red para reintentar'}

        logger.info(f"🔄 Iniciando reintentos diferidos para {len(failed_users)} usuarios")
        self.metrics.set_total_usuarios(len(failed_users))

        # Procesar reintentos
        usuarios_exitosos = []
        usuarios_fallidos = []

        batch_size = self.get_config()['batch_size']
        for i in range(0, len(failed_users), batch_size):
            lote = failed_users[i:i + batch_size]
            logger.info(f"🔄 Procesando lote de reintento {i//batch_size + 1} ({len(lote)} usuarios)")

            exitosos_lote, fallidos_lote = self.procesar_lote(lote, frase_data, is_retry=True)
            usuarios_exitosos.extend(exitosos_lote)
            usuarios_fallidos.extend(fallidos_lote)

            # Registrar reintentos diferidos en métricas
            for _ in exitosos_lote:
                self.metrics.add_deferred_retry()

        # Si aún hay fallos de red, guardar para el próximo reintento
        network_failures = [item for item in usuarios_fallidos if item.get('is_network_error', False)]
        if network_failures:
            self.failed_users_manager.save_failed_users(network_failures, frase_data)
        else:
            self.failed_users_manager.clear_failed_users()

        return {
            'success': True,
            'is_retry': True,
            'frase_id': frase_data['id'],
            'total_usuarios': len(failed_users),
            'exitosos': len(usuarios_exitosos),
            'fallidos': len(usuarios_fallidos),
            'tasa_exito': round((len(usuarios_exitosos) / len(failed_users) * 100), 2),
            'usuarios_exitosos': usuarios_exitosos,
            'usuarios_fallidos': usuarios_fallidos,
            'frase': frase_data['frase'][:100],
            'metricas': self.metrics.finalizar()
        }

    def procesar_envios(self) -> Dict[str, Any]:
        """Procesa todos los envíos del día con procesamiento por lotes y reintentos diferidos"""
        # Primero verificar si hay reintentos diferidos pendientes
        retry_result = self.procesar_reintentos_diferidos()
        if retry_result.get('success'):
            return retry_result

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

        self.metrics.set_total_usuarios(len(usuarios_activos))
        logger.info(f"📧 Iniciando envío masivo de frase: '{frase_data['frase'][:50]}...'")
        logger.info(f"👥 Total de usuarios activos: {len(usuarios_activos)}")

        # Procesar por lotes
        batch_size = self.get_config()['batch_size']
        usuarios_exitosos = []
        usuarios_fallidos = []

        for i in range(0, len(usuarios_activos), batch_size):
            lote = usuarios_activos[i:i + batch_size]
            logger.info(f"📦 Procesando lote {i//batch_size + 1} ({len(lote)} usuarios)")

            exitosos_lote, fallidos_lote = self.procesar_lote(lote, frase_data)
            usuarios_exitosos.extend(exitosos_lote)
            usuarios_fallidos.extend(fallidos_lote)

        # Separar errores de red para reintentos diferidos
        network_failures = [item for item in usuarios_fallidos if item.get('is_network_error', False)]
        other_failures = [item for item in usuarios_fallidos if not item.get('is_network_error', False)]

        # Guardar errores de red para reintentos diferidos
        if network_failures:
            logger.warning(f"🌐 {len(network_failures)} usuarios fallaron por errores de red. Programando reintento en {EMAIL_CONFIG['retry_delay_minutes']} minutos.")
            self.failed_users_manager.save_failed_users(network_failures, frase_data)

        # Finalizar métricas
        metricas_finales = self.metrics.finalizar()

        # Resumen de resultados
        resultados = {
            'success': True,
            'frase_id': frase_data['id'],
            'total_usuarios': len(usuarios_activos),
            'exitosos': len(usuarios_exitosos),
            'fallidos': len(usuarios_fallidos),
            'errores_red': len(network_failures),
            'otros_errores': len(other_failures),
            'tasa_exito': round((len(usuarios_exitosos) / len(usuarios_activos) * 100), 2),
            'usuarios_exitosos': usuarios_exitosos,
            'usuarios_fallidos': usuarios_fallidos,
            'frase': frase_data['frase'][:100],
            'metricas': metricas_finales
        }

        return resultados

    def generar_reporte(self, resultados: Dict[str, Any]) -> None:
        """Genera reporte detallado del proceso con métricas adicionales"""
        logger.info("=" * 60)
        logger.info("📊 REPORTE FINAL DEL ENVÍO")
        logger.info("=" * 60)

        if not resultados.get('success'):
            logger.error(f"❌ PROCESO FALLÓ: {resultados.get('error', 'Error desconocido')}")
            return

        is_retry = resultados.get('is_retry', False)
        if is_retry:
            logger.info("🔄 REPORTE DE REINTENTOS DIFERIDOS")

        logger.info(f"📝 Frase enviada: '{resultados['frase']}...'")
        logger.info(f"👥 Total usuarios: {resultados['total_usuarios']}")
        logger.info(f"✅ Envíos exitosos: {resultados['exitosos']}")
        logger.info(f"❌ Envíos fallidos: {resultados['fallidos']}")
        logger.info(f"📈 Tasa de éxito: {resultados['tasa_exito']}%")

        # Información específica de errores de red
        if not is_retry and 'errores_red' in resultados:
            logger.info(f"🌐 Errores de red: {resultados['errores_red']}")
            logger.info(f"🔧 Otros errores: {resultados['otros_errores']}")
            if resultados['errores_red'] > 0:
                logger.info(f"⏰ Reintento programado en {EMAIL_CONFIG['retry_delay_minutes']} minutos")

        # Métricas de rendimiento
        metricas = resultados['metricas']
        logger.info(f"⏱️ Tiempo total de ejecución: {metricas['tiempo_total']:.2f} segundos")
        logger.info(f"⚡ Tiempo promedio por envío: {metricas['tiempo_promedio_envio']:.2f} segundos")
        if metricas['tiempo_total'] > 0:
            logger.info(f"📈 Tasa de envío: {resultados['exitosos']/metricas['tiempo_total']:.2f} emails/segundo")

        # Información de reintentos diferidos
        if metricas.get('reintentos_diferidos', 0) > 0:
            logger.info(f"🔄 Reintentos diferidos exitosos: {metricas['reintentos_diferidos']}")

        # Detalles por tipo de suscripción
        usuarios_exitosos = resultados['usuarios_exitosos']
        premium_exitosos = [u for u in usuarios_exitosos if u.get('tipo_suscripcion', '').lower() == 'premium']
        gratuitos_exitosos = [u for u in usuarios_exitosos if u.get('tipo_suscripcion', '').lower() == 'gratuito']

        logger.info(f"💎 Usuarios Premium exitosos: {len(premium_exitosos)}")
        logger.info(f"📧 Usuarios Gratuitos exitosos: {len(gratuitos_exitosos)}")

        # Mostrar errores si los hay
        if metricas.get('errores'):
            logger.warning("⚠️ ERRORES ENCONTRADOS:")
            for error in metricas['errores'][:10]:  # Mostrar solo los primeros 10
                logger.warning(f"   - {error}")
            if len(metricas['errores']) > 10:
                logger.warning(f"   ... y {len(metricas['errores']) - 10} errores más")

        # Estadísticas adicionales
        try:
            stats = self.frase_service.get_estadisticas_envios()
            logger.info(f"📊 Estadísticas del día:")
            logger.info(f"   - Total envíos hoy: {stats['total_hoy']}")
            logger.info(f"   - Exitosos hoy: {stats['exitosos_hoy']}")
            logger.info(f"   - Tasa éxito hoy: {stats['tasa_exito_hoy']}%")
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron obtener estadísticas adicionales: {e}")

        logger.info("=" * 60)


def main():
    """Función principal del script con manejo mejorado de errores"""
    logger.info("🚀 " + "=" * 50)
    logger.info("🚀 INICIANDO SISTEMA DE FRASES DIARIAS MEJORADO")
    logger.info("🚀 " + "=" * 50)

    try:
        # Inicializar manager
        manager = FraseDiariaManager()

        # Validar configuración
        if not manager.validar_configuracion():
            logger.error("❌ Configuración inválida. Terminando proceso.")
            return 1

        # Procesar envíos
        logger.info("📧 Iniciando proceso de envíos...")
        resultados = manager.procesar_envios()

        # Generar reporte
        manager.generar_reporte(resultados)

        # Mensaje final
        if resultados.get('success'):
            is_retry = resultados.get('is_retry', False)
            if resultados['exitosos'] == resultados['total_usuarios']:
                if is_retry:
                    logger.info("🎉 ¡REINTENTOS COMPLETADOS PERFECTAMENTE! Todos los envíos fueron exitosos.")
                else:
                    logger.info("🎉 ¡PROCESO COMPLETADO PERFECTAMENTE! Todos los envíos fueron exitosos.")
                return 0
            elif resultados['exitosos'] > 0:
                if is_retry:
                    logger.info(f"✅ REINTENTOS COMPLETADOS PARCIALMENTE. {resultados['exitosos']}/{resultados['total_usuarios']} envíos exitosos.")
                else:
                    logger.info(f"✅ PROCESO COMPLETADO PARCIALMENTE. {resultados['exitosos']}/{resultados['total_usuarios']} envíos exitosos.")
                    if resultados.get('errores_red', 0) > 0:
                        logger.info(f"⏰ {resultados['errores_red']} usuarios serán reintentados en {EMAIL_CONFIG['retry_delay_minutes']} minutos.")
                return 0
            else:
                logger.error("💥 PROCESO FALLÓ COMPLETAMENTE. No se pudo enviar a ningún usuario.")
                return 1
        else:
            logger.error("💥 PROCESO FALLÓ. Ver detalles arriba.")
            return 1

    except Exception as e:
        logger.critical(f"💥 ERROR CRÍTICO EN MAIN: {e}", exc_info=True)
        return 1

    finally:
        logger.info("🏁 " + "=" * 50)
        logger.info("🏁 PROCESO FINALIZADO")
        logger.info("🏁 " + "=" * 50)


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)