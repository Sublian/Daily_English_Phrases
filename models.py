import re
import logging
from datetime import datetime, timedelta
from database import DatabaseManager
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

class UserService:
    """Servicio para gestión de usuarios"""

    @staticmethod
    def validate_email(email):
        """Valida formato de email"""
        patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(patron, email) is not None

    @staticmethod
    def hash_password(password):
        """Genera hash de contraseña"""
        return generate_password_hash(password)

    @staticmethod
    def get_all_users():
        """Obtiene todos los usuarios"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, email, nombre, activo, tipo_suscripcion,
                       fecha_registro, fecha_ultimo_envio
                FROM usuarios
                ORDER BY fecha_registro DESC
            """)
            return cursor.fetchall()

    @staticmethod
    def get_user_by_email(email):
        """Obtiene un usuario por su email"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM usuarios WHERE email = %s', (email,))
            return cursor.fetchone()

    @staticmethod
    def create_user(email, nombre=None, password=None):
        """Crea un nuevo usuario"""
        if not UserService.validate_email(email):
            return False, "Email inválido"

        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()

                # Verificar si el email ya existe
                cursor.execute('SELECT id FROM usuarios WHERE email = %s', (email,))
                if cursor.fetchone():
                    return False, "El email ya está registrado"

                # Crear el usuario con rol 'pendiente' si no tiene contraseña
                password_hash = generate_password_hash(password) if password else None
                rol = 'usuario' if password else 'pendiente'

                cursor.execute("""
                    INSERT INTO usuarios (email, nombre, password_hash, activo, tipo_suscripcion, rol)
                    VALUES (%s, %s, %s, TRUE, 'gratuito', %s)
                """, (email, nombre, password_hash, rol))

                # Obtener el ID del usuario recién creado
                user_id = cursor.lastrowid
                conn.commit()

                # Enviar notificación al administrador
                UserService._notify_admin_new_user(email, nombre)

                # Si no tiene contraseña, generar token y enviar correo de confirmación
                if not password:
                    from token_service import TokenService
                    success, token = TokenService.crear_token_validacion(user_id, 'email_confirmacion')

                    if success:
                        UserService._send_confirmation_email(email, nombre, token)
                        return True, "Usuario agregado exitosamente. Se ha enviado un correo de confirmación."
                    else:
                        logger.error(f"Error al generar token para usuario {user_id}: {token}")
                        return True, "Usuario agregado exitosamente, pero hubo un error al enviar el correo de confirmación."

                return True, "Usuario agregado exitosamente"

        except Exception as err:
            logger.error(f"Error al agregar usuario: {err}")
            return False, "Error al agregar usuario"

    @staticmethod
    def update_user(user_id, activo=None, tipo_suscripcion=None):
        """Actualiza un usuario"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []

                if activo is not None:
                    updates.append("activo = %s")
                    params.append(activo)

                if tipo_suscripcion:
                    updates.append("tipo_suscripcion = %s")
                    params.append(tipo_suscripcion)

                if updates:
                    query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
                    params.append(user_id)
                    cursor.execute(query, params)
                    conn.commit()
                    return True, "Usuario actualizado exitosamente"
                return False, "No hay cambios para actualizar"

        except Exception as err:
            logger.error(f"Error al actualizar usuario: {err}")
            return False, "Error al actualizar usuario"

    @staticmethod
    def update_user_profile(user_id, nombre=None):
        """Actualiza el perfil de un usuario"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE usuarios SET nombre = %s WHERE id = %s',
                              (nombre, user_id))
                conn.commit()
                return True, "Perfil actualizado exitosamente"

        except Exception as err:
            logger.error(f"Error al actualizar perfil: {err}")
            return False, "Error al actualizar perfil"

    @staticmethod
    def update_user_password(user_id, current_password, new_password):
        """Actualiza la contraseña de un usuario"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # Verificar contraseña actual
                cursor.execute('SELECT password_hash FROM usuarios WHERE id = %s', (user_id,))
                user_data = cursor.fetchone()

                if not user_data or not check_password_hash(user_data['password_hash'], current_password):
                    return False, "La contraseña actual es incorrecta"

                # Actualizar contraseña
                new_password_hash = generate_password_hash(new_password)
                cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = %s',
                              (new_password_hash, user_id))
                conn.commit()
                return True, "Contraseña actualizada exitosamente"

        except Exception as err:
            logger.error(f"Error al actualizar contraseña: {err}")
            return False, "Error al actualizar contraseña"

    @staticmethod
    def _notify_admin_new_user(email, nombre):
        """Envía notificación al administrador sobre nuevo usuario"""
        try:
            from email_service import EmailService
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Configuración de email desde Config
            email_config = {
                'user': Config.EMAIL_USER,
                'password': Config.EMAIL_PASSWORD,
                'smtp_server': Config.SMTP_SERVER,
                'smtp_port': Config.SMTP_PORT
            }

            # Crear mensaje de notificación
            msg = MIMEMultipart()
            msg['Subject'] = '🎉 Nuevo Suscriptor en Daily English Phrases'
            msg['From'] = email_config['user']
            msg['To'] = Config.ADMIN_EMAIL  # Necesitaremos agregar esta configuración

            # Contenido del mensaje
            nombre_display = nombre if nombre else 'Sin nombre'
            fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                        <h2 style="color: #2c3e50; text-align: center;">🎉 ¡Nuevo Suscriptor!</h2>

                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <h3 style="color: #27ae60; margin-top: 0;">Detalles del nuevo suscriptor:</h3>
                            <p><strong>📧 Email:</strong> {email}</p>
                            <p><strong>👤 Nombre:</strong> {nombre_display}</p>
                            <p><strong>📅 Fecha de registro:</strong> {fecha_actual}</p>
                            <p><strong>🎯 Tipo de suscripción:</strong> Gratuito</p>
                        </div>

                        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; border-left: 4px solid #27ae60;">
                            <p style="margin: 0;"><strong>¡Excelente!</strong> Un nuevo usuario se ha unido a nuestra comunidad de aprendizaje de inglés.</p>
                        </div>

                        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">

                        <p style="text-align: center; color: #7f8c8d; font-size: 12px;">
                            Este es un mensaje automático del sistema Daily English Phrases<br>
                            Generado el {fecha_actual}
                        </p>
                    </div>
                </body>
            </html>
            """

            msg.attach(MIMEText(html_content, 'html'))

            # Enviar el correo
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['user'], email_config['password'])
                server.send_message(msg)

            logger.info(f"✅ Notificación de nuevo usuario enviada al administrador: {email}")

        except Exception as e:
            logger.error(f"❌ Error al enviar notificación de nuevo usuario: {e}")
            # No fallar la creación del usuario si falla la notificación

    @staticmethod
    def _send_confirmation_email(email, nombre, token):
        """Envía correo de confirmación al usuario con token de validación"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from flask import url_for

            # Configuración de email desde Config
            email_config = {
                'user': Config.EMAIL_USER,
                'password': Config.EMAIL_PASSWORD,
                'smtp_server': Config.SMTP_SERVER,
                'smtp_port': Config.SMTP_PORT
            }

            # Crear mensaje de confirmación
            msg = MIMEMultipart()
            msg['Subject'] = '📧 Confirma tu suscripción a Daily English Phrases'
            msg['From'] = email_config['user']
            msg['To'] = email

            # Contenido del mensaje
            nombre_display = nombre if nombre else 'Nuevo suscriptor'

            # URL de confirmación (necesitaremos el dominio base)
            confirmation_url = f"https://subliandev.pythonanywhere.com/confirmar-email/{token}"

            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                        <h2 style="color: #2c3e50; text-align: center;">🎉 ¡Bienvenido a Daily English Phrases!</h2>

                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <p>Hola <strong>{nombre_display}</strong>,</p>
                            <p>¡Gracias por suscribirte a Daily English Phrases! Para completar tu registro y comenzar a recibir frases inspiradoras en inglés, necesitas confirmar tu dirección de correo electrónico.</p>
                        </div>

                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{confirmation_url}"
                               style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                                ✅ Confirmar mi suscripción
                            </a>
                        </div>

                        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; border-left: 4px solid #27ae60;">
                            <p style="margin: 0;"><strong>¿Qué obtienes al confirmar?</strong></p>
                            <ul>
                                <li>📚 Frases diarias en inglés con traducción</li>
                                <li>🎯 Contenido personalizado según tu nivel</li>
                                <li>📊 Estadísticas de tu progreso</li>
                                <li>🔐 Acceso a tu perfil personalizado</li>
                            </ul>
                        </div>

                        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">

                        <p style="color: #7f8c8d; font-size: 12px;">
                            Si no puedes hacer clic en el botón, copia y pega este enlace en tu navegador:<br>
                            <a href="{confirmation_url}">{confirmation_url}</a>
                        </p>

                        <p style="text-align: center; color: #7f8c8d; font-size: 12px;">
                            Este enlace expira en 24 horas por seguridad.<br>
                            Daily English Phrases - Tu compañero de aprendizaje diario
                        </p>
                    </div>
                </body>
            </html>
            """

            msg.attach(MIMEText(html_content, 'html'))

            # Enviar el correo
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['user'], email_config['password'])
                server.send_message(msg)

            logger.info(f"✅ Correo de confirmación enviado a: {email}")

        except Exception as e:
            logger.error(f"❌ Error al enviar correo de confirmación a {email}: {e}")
            # No fallar la creación del usuario si falla el envío del correo

class StatsService:
    """Servicio para estadísticas del dashboard"""

    @staticmethod
    def get_dashboard_stats():
        """Obtiene estadísticas para el dashboard con zona horaria GMT-5"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # Obtener fecha/hora actual en GMT-5 (UTC-5)
                now_utc = datetime.utcnow()
                now_gmt5 = now_utc - timedelta(hours=5)  # Ajuste manual a GMT-5
                today_gmt5 = now_gmt5.date()

                stats = {
                    'usuarios_activos': 0,
                    'usuarios_premium': 0,
                    'usuarios_pendientes': 0,
                    'envios_hoy': 0,
                    'envios_semana': 0,
                    'envios_mes': 0,
                    'fecha_consulta': now_gmt5.strftime('%Y-%m-%d %H:%M:%S'),
                    'zona_horaria': 'GMT-5 (Manual)',
                    'status': 'success'
                }

                try:
                    # Consultas que no dependen de fecha (sin cambios)
                    cursor.execute('SELECT COUNT(*) as count FROM usuarios WHERE activo = 1')
                    stats['usuarios_activos'] = cursor.fetchone()['count'] or 0

                    cursor.execute('SELECT COUNT(*) as count FROM usuarios WHERE tipo_suscripcion = "premium"')
                    stats['usuarios_premium'] = cursor.fetchone()['count'] or 0

                    cursor.execute('SELECT COUNT(*) as count FROM usuarios WHERE rol = "pendiente"')
                    stats['usuarios_pendientes'] = cursor.fetchone()['count'] or 0

                    # CONSULTAS CON AJUSTE DE ZONA HORARIA (GMT-5)

                    # Envíos exitosos hoy (GMT-5)
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM trazabilidad_envio
                        WHERE DATE(enviado_en - INTERVAL 5 HOUR) = %s
                        AND resultado = 'exito'
                    """, (today_gmt5,))
                    stats['envios_hoy'] = cursor.fetchone()['count'] or 0

                    # Envíos exitosos esta semana (GMT-5)
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM trazabilidad_envio
                        WHERE YEARWEEK(enviado_en - INTERVAL 5 HOUR, 1) = YEARWEEK(%s, 1)
                        AND resultado = 'exito'
                    """, (today_gmt5,))
                    stats['envios_semana'] = cursor.fetchone()['count'] or 0

                    # Envíos exitosos este mes (GMT-5)
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM trazabilidad_envio
                        WHERE YEAR(enviado_en - INTERVAL 5 HOUR) = YEAR(%s)
                        AND MONTH(enviado_en - INTERVAL 5 HOUR) = MONTH(%s)
                        AND resultado = 'exito'
                    """, (today_gmt5, today_gmt5))
                    stats['envios_mes'] = cursor.fetchone()['count'] or 0

                except Exception as db_error:
                    stats['status'] = f'db_error: {str(db_error)}'

                return stats

        except Exception as e:
            return {
                'status': f'error: {str(e)}',
                'fecha_consulta': (datetime.utcnow() - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S'),
                'zona_horaria': 'GMT-5 (Manual)'
            }

    @staticmethod
    def get_user_stats(user_id):
        """Obtiene estadísticas específicas de un usuario"""
        try:
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                stats = {
                    'correos_recibidos': 0,
                    'fecha_registro': None
                }

                # Obtener cantidad de correos recibidos exitosamente
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM trazabilidad_envio
                    WHERE usuario_id = %s AND resultado = 'exito'
                """, (user_id,))
                stats['correos_recibidos'] = cursor.fetchone()['count'] or 0

                # Obtener fecha de registro del usuario
                cursor.execute("""
                    SELECT fecha_registro
                    FROM usuarios
                    WHERE id = %s
                """, (user_id,))
                result = cursor.fetchone()
                if result and result['fecha_registro']:
                    stats['fecha_registro'] = result['fecha_registro']

                return stats

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del usuario {user_id}: {str(e)}")
            return {
                'correos_recibidos': 0,
                'fecha_registro': None
            }