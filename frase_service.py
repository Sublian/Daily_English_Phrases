import logging
from datetime import datetime
from typing import Optional, Dict, Any
from database import DatabaseManager
from config import Config

logger = logging.getLogger(__name__)

class FraseService:
    """Servicio para operaciones relacionadas con frases"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def obtener_frase_dia(self, fecha: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Obtiene la frase del día basada en el día del año"""
        if fecha is None:
            fecha = datetime.now(Config.LOCAL_TZ)

        dia_del_ano = fecha.timetuple().tm_yday
        logger.info(f"🔍 Buscando frase para el día {dia_del_ano} del año")

        query = "SELECT * FROM frases_dia WHERE dia_del_ano = %s"
        
        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (dia_del_ano,))
                frase = cursor.fetchone()

                if frase:
                    logger.info(f"✅ Frase encontrada: ID {frase['id']} - '{frase['frase'][:50]}...'")
                else:
                    logger.warning(f"⚠️ No se encontró frase para el día {dia_del_ano}")

                return frase

    def registrar_envio(self, frase_id: int, usuario_id: int, resultado: str, 
                       descripcion_error: Optional[str] = None) -> bool:
        """Registra el resultado del envío en la base de datos"""
        try:
            query = """
                INSERT INTO trazabilidad_envio
                (frase_id, usuario_id, resultado, descripcion_error, enviado_en)
                VALUES (%s, %s, %s, %s, NOW())
            """
            
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (frase_id, usuario_id, resultado, descripcion_error))
                    conn.commit()

            logger.info(f"📝 Envío registrado: frase_id={frase_id}, usuario_id={usuario_id}, resultado={resultado}")
            return True
            
        except Exception as err:
            logger.error(f"❌ Error registrando envío: {err}")
            return False

    def registrar_envios_masivos(self, frase_id: int, resultados_envio: Dict[str, Any]) -> None:
        """Registra múltiples envíos de forma masiva"""
        exitosos = resultados_envio.get('usuarios_exitosos', [])
        fallidos = resultados_envio.get('usuarios_fallidos', [])
        
        # Registrar envíos exitosos
        for usuario in exitosos:
            self.registrar_envio(frase_id, usuario['id'], 'exito')
        
        # Registrar envíos fallidos
        for usuario_error in fallidos:
            self.registrar_envio(
                frase_id, 
                usuario_error['usuario']['id'], 
                'error', 
                usuario_error.get('error', 'Error no especificado')
            )
        
        logger.info(f"📊 Registros masivos completados - Exitosos: {len(exitosos)}, Fallidos: {len(fallidos)}")

    def get_estadisticas_envios(self) -> Dict[str, Any]:
        """Obtiene estadísticas de envíos"""
        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                # Total de envíos hoy
                cursor.execute("""
                    SELECT COUNT(*) as total_hoy
                    FROM trazabilidad_envio 
                    WHERE DATE(enviado_en) = CURDATE()
                """)
                total_hoy = cursor.fetchone()['total_hoy']
                
                # Envíos exitosos hoy
                cursor.execute("""
                    SELECT COUNT(*) as exitosos_hoy
                    FROM trazabilidad_envio 
                    WHERE DATE(enviado_en) = CURDATE() AND resultado = 'exito'
                """)
                exitosos_hoy = cursor.fetchone()['exitosos_hoy']
                
                # Total general
                cursor.execute("SELECT COUNT(*) as total FROM trazabilidad_envio")
                total_general = cursor.fetchone()['total']
                
                return {
                    'total_hoy': total_hoy,
                    'exitosos_hoy': exitosos_hoy,
                    'fallidos_hoy': total_hoy - exitosos_hoy,
                    'total_general': total_general,
                    'tasa_exito_hoy': round((exitosos_hoy / total_hoy * 100) if total_hoy > 0 else 0, 2)
                }