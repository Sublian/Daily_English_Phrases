import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from database import DatabaseManager

logger = logging.getLogger(__name__)

class TokenService:
    """Servicio para gestión de tokens de validación"""
    
    @staticmethod
    def generar_token() -> str:
        """Genera un token seguro de 32 caracteres"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def crear_token_validacion(usuario_id: int, tipo: str = 'email_confirmacion', 
                              horas_expiracion: int = 24) -> Tuple[bool, str]:
        """Crea un token de validación para un usuario"""
        try:
            token = TokenService.generar_token()
            fecha_expiracion = datetime.now() + timedelta(hours=horas_expiracion)
            
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Invalidar tokens anteriores del mismo tipo para este usuario
                cursor.execute("""
                    UPDATE tokens_validacion 
                    SET usado = TRUE 
                    WHERE usuario_id = %s AND tipo = %s AND usado = FALSE
                """, (usuario_id, tipo))
                
                # Crear nuevo token
                cursor.execute("""
                    INSERT INTO tokens_validacion 
                    (usuario_id, token, tipo, fecha_expiracion)
                    VALUES (%s, %s, %s, %s)
                """, (usuario_id, token, tipo, fecha_expiracion))
                
                conn.commit()
                logger.info(f"✅ Token de {tipo} creado para usuario {usuario_id}")
                return True, token
                
        except Exception as e:
            logger.error(f"❌ Error al crear token para usuario {usuario_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def validar_token(token: str, tipo: str = 'email_confirmacion') -> Tuple[bool, Optional[int], str]:
        """Valida un token sin marcarlo como usado y retorna (es_valido, usuario_id, mensaje)"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Buscar token válido
                cursor.execute("""
                    SELECT usuario_id, fecha_expiracion, usado
                    FROM tokens_validacion 
                    WHERE token = %s AND tipo = %s
                """, (token, tipo))
                
                token_data = cursor.fetchone()
                
                if not token_data:
                    return False, None, "Token no válido"
                
                if token_data['usado']:
                    return False, None, "Token ya utilizado"
                
                if datetime.now() > token_data['fecha_expiracion']:
                    return False, None, "Token expirado"
                
                logger.info(f"✅ Token validado para usuario {token_data['usuario_id']}")
                return True, token_data['usuario_id'], "Token válido"
                
        except Exception as e:
            logger.error(f"❌ Error al validar token: {e}")
            return False, None, f"Error interno: {str(e)}"
    
    @staticmethod
    def limpiar_tokens_expirados() -> int:
        """Limpia tokens expirados y retorna cantidad eliminada"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM tokens_validacion 
                    WHERE fecha_expiracion < NOW()
                """)
                
                eliminados = cursor.rowcount
                conn.commit()
                
                if eliminados > 0:
                    logger.info(f"🧹 Tokens expirados eliminados: {eliminados}")
                
                return eliminados
                
        except Exception as e:
            logger.error(f"❌ Error al limpiar tokens expirados: {e}")
            return 0
    
    @staticmethod
    def marcar_token_usado(token: str) -> bool:
        """Marca un token específico como usado"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE tokens_validacion 
                    SET usado = TRUE 
                    WHERE token = %s
                """, (token,))
                
                conn.commit()
                logger.info(f"✅ Token marcado como usado")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error al marcar token como usado: {e}")
            return False