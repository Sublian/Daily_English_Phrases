import re
import logging
from typing import List, Dict, Any, Optional
from database import DatabaseManager

logger = logging.getLogger(__name__)

class UserService:
    """Servicio para gestión de usuarios"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @staticmethod
    def validate_email(email: str) -> bool:
        """Valida formato de email"""
        patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(patron, email) is not None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Obtiene todos los usuarios"""
        query = """
            SELECT u.*, 
                   COUNT(te.id) as total_envios,
                   MAX(te.enviado_en) as ultimo_envio
            FROM usuarios u
            LEFT JOIN trazabilidad_envio te ON u.id = te.usuario_id
            GROUP BY u.id
            ORDER BY u.fecha_registro DESC
        """
        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query)
                return cursor.fetchall()

    def get_active_users(self) -> List[Dict[str, Any]]:
        """Obtiene usuarios activos para envío de emails"""
        query = """
            SELECT id, email, nombre, tipo_suscripcion, fecha_registro
            FROM usuarios 
            WHERE activo = TRUE 
            ORDER BY tipo_suscripcion DESC, nombre ASC
        """
        
        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query)
                usuarios = cursor.fetchall()
                
                logger.info(f"👥 Usuarios activos encontrados: {len(usuarios)}")
                
                # Log por tipo de suscripción
                premium_count = sum(1 for u in usuarios if u.get('tipo_suscripcion', '').lower() == 'premium')
                gratuito_count = len(usuarios) - premium_count
                
                logger.info(f"💎 Usuarios Premium: {premium_count}")
                logger.info(f"📧 Usuarios Gratuitos: {gratuito_count}")
                
                return usuarios

    def create_user(self, email: str, nombre: Optional[str] = None, password: Optional[str] = None) -> tuple[bool, str]:
        """Crea un nuevo usuario con estado pendiente y envía correo de confirmación"""
        if not self.validate_email(email):
            return False, "Email inválido"

        try:
            # Verificar si el usuario ya existe
            existing_user = self.get_user_by_email(email)
            if existing_user:
                return False, "El email ya está registrado"
                
            # Crear usuario con rol 'pendiente'
            query = """
                INSERT INTO usuarios (email, nombre, activo, tipo_suscripcion, rol) 
                VALUES (%s, %s, TRUE, 'gratuito', 'pendiente')
            """
            
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (email, nombre))
                    conn.commit()
                    user_id = cursor.lastrowid
            
            # Crear token de validación
            from token_service import TokenService
            token_success, token = TokenService.crear_token_validacion(user_id, 'email_confirmacion', 24)
            
            if not token_success:
                logger.error(f"❌ Error al crear token para {email}: {token}")
                return False, "Error al generar token de validación"
            
            # Enviar correo de confirmación
            try:
                from email_service import EmailService
                from config import Config
                from flask import url_for, request
                
                # Generar URL de confirmación
                base_url = request.url_root if request else 'http://localhost:5000/'
                confirmation_url = f"{base_url}confirmar-email/{token}"
                
                # Crear datos para el correo de confirmación
                frase_data = {
                    'frase': '¡Confirma tu suscripción!',
                    'significado': f'Hola {nombre or "Amigo"}, confirma tu email para activar tu cuenta.',
                    'ejemplo': f'Haz clic en el siguiente enlace para confirmar: {confirmation_url}'
                }
                
                # Crear usuario para el correo
                usuario = {
                    'id': user_id,
                    'email': email,
                    'nombre': nombre or 'Amigo',
                    'tipo_suscripcion': 'gratuito'
                }
                
                # Configuración de email
                email_config = {
                    'user': Config.EMAIL_USER,
                    'password': Config.EMAIL_PASSWORD,
                    'smtp_server': Config.SMTP_SERVER,
                    'smtp_port': Config.SMTP_PORT
                }
                
                # Enviar correo de confirmación
                email_service = EmailService(email_config)
                email_service.enviar_correo(frase_data, usuario)
                logger.info(f"✅ Correo de confirmación enviado a: {email}")
                
            except Exception as email_err:
                logger.error(f"❌ Error al enviar correo de confirmación a {email}: {email_err}")
                # No fallamos la creación del usuario si falla el correo
                
            logger.info(f"✅ Usuario creado con estado pendiente: {email}")
            return True, "Usuario registrado exitosamente. Revisa tu correo para confirmar tu cuenta."
            
        except Exception as err:
            logger.error(f"❌ Error al crear usuario {email}: {err}")
            if "Duplicate entry" in str(err):
                return False, "El email ya está registrado"
            return False, "Error al agregar usuario"

    def update_user(self, user_id: int, activo: Optional[bool] = None, 
                   tipo_suscripcion: Optional[str] = None, rol: Optional[str] = None) -> tuple[bool, str]:
        """Actualiza un usuario"""
        try:
            updates = []
            params = []
            
            if activo is not None:
                updates.append("activo = %s")
                params.append(activo)
            
            if tipo_suscripcion is not None:
                updates.append("tipo_suscripcion = %s")
                params.append(tipo_suscripcion)
            
            if rol is not None:
                updates.append("rol = %s")
                params.append(rol)
            
            if not updates:
                return False, "No hay cambios para actualizar"
            
            params.append(user_id)
            query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
            
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    conn.commit()
                    
            logger.info(f"✅ Usuario {user_id} actualizado")
            return True, "Usuario actualizado exitosamente"
            
        except Exception as err:
            logger.error(f"❌ Error al actualizar usuario {user_id}: {err}")
            return False, "Error al actualizar usuario"

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Obtiene un usuario por email"""
        query = "SELECT * FROM usuarios WHERE email = %s"
        
        with self.db_manager.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (email,))
                return cursor.fetchone()
    
    @staticmethod
    def create_user(email: str, nombre: Optional[str] = None, password: Optional[str] = None) -> tuple[bool, str]:
        """Método estático para crear usuario desde rutas"""
        from database import DatabaseManager
        db_manager = DatabaseManager()
        service = UserService(db_manager)
        return service.create_user(email, nombre, password)