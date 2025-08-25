import mysql.connector
from mysql.connector import pooling
import logging
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gestor de conexiones a la base de datos con pool de conexiones"""
    pool = None

    @classmethod
    def initialize_pool(cls):
        if cls.pool is None:
            try:
                pool_config = {
                    'user': Config.DB_CONFIG['user'],
                    'password': Config.DB_CONFIG['password'],
                    'host': Config.DB_CONFIG['host'],
                    'database': Config.DB_CONFIG['database'],
                    'charset': Config.DB_CONFIG['charset'],
                    'autocommit': Config.DB_CONFIG['autocommit'],
                    'pool_name': 'frases_pool',
                    'pool_size': 5,
                    'pool_reset_session': True,
                    'collation': 'utf8mb4_unicode_ci'
                }
                cls.pool = mysql.connector.pooling.MySQLConnectionPool(**pool_config)
                logger.info("✅ Pool de conexiones creado exitosamente")
            except mysql.connector.Error as err:
                logger.critical(f"💥 Error creando pool de conexiones: {err}")
                raise

    @classmethod
    @contextmanager
    def get_connection(cls):
        if cls.pool is None:
            cls.initialize_pool()
        conn = None
        try:
            conn = cls.pool.get_connection()
            yield conn
        except mysql.connector.Error as err:
            logger.error(f"❌ Error de conexión a la base de datos: {err}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    @classmethod
    def execute_query(cls, query: str, params=None, fetch_one=False, fetch_all=False, commit=False):
        with cls.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())

                if commit:
                    conn.commit()

                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()

                return cursor.rowcount if commit else True

    @classmethod
    def get_stats(cls):
        with cls.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                # Total de envíos
                cursor.execute("SELECT COUNT(*) as total FROM trazabilidad_envio")
                total_envios = cursor.fetchone()['total']

                # Envíos exitosos
                cursor.execute("SELECT COUNT(*) as exitosos FROM trazabilidad_envio WHERE resultado = 'exito'")
                envios_exitosos = cursor.fetchone()['exitosos']

                # Total de usuarios
                cursor.execute("SELECT COUNT(*) as total FROM usuarios")
                total_usuarios = cursor.fetchone()['total']

                # Usuarios activos
                cursor.execute("SELECT COUNT(*) as activos FROM usuarios WHERE activo = TRUE")
                usuarios_activos = cursor.fetchone()['activos']

                # Último envío
                cursor.execute("""
                    SELECT te.enviado_en, te.resultado, fd.frase, u.email, u.nombre
                    FROM trazabilidad_envio te
                    JOIN frases_dia fd ON te.frase_id = fd.id
                    LEFT JOIN usuarios u ON te.usuario_id = u.id
                    ORDER BY te.enviado_en DESC
                    LIMIT 1
                """)
                ultimo_envio = cursor.fetchone()

                # Envíos por día (últimos 7 días)
                cursor.execute("""
                    SELECT DATE(enviado_en) as fecha,
                           COUNT(*) as total,
                           SUM(CASE WHEN resultado = 'exito' THEN 1 ELSE 0 END) as exitosos
                    FROM trazabilidad_envio
                    WHERE enviado_en >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    GROUP BY DATE(enviado_en)
                    ORDER BY fecha DESC
                """)
                envios_recientes = cursor.fetchall()

                # Total de frases disponibles
                cursor.execute("SELECT COUNT(*) as total FROM frases_dia")
                total_frases = cursor.fetchone()['total']

                return {
                    'total_envios': total_envios,
                    'envios_exitosos': envios_exitosos,
                    'total_usuarios': total_usuarios,
                    'usuarios_activos': usuarios_activos,
                    'tasa_exito': round((envios_exitosos / total_envios * 100) if total_envios > 0 else 0, 2),
                    'ultimo_envio': ultimo_envio,
                    'envios_recientes': envios_recientes,
                    'total_frases': total_frases
                }

    @classmethod
    def get_users(cls, only_active=True):
        """Obtiene lista de usuarios, opcionalmente solo activos"""
        query = "SELECT id, email, nombre, activo, tipo_suscripcion, fecha_registro, fecha_ultimo_envio, preferencias FROM usuarios"
        params = ()
        if only_active:
            query += " WHERE activo = TRUE"
        with cls.get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                users = cursor.fetchall()
        return users

    @classmethod
    def update_user(cls, user_id: int, data: dict):
        """Actualiza campos del usuario identificado por user_id.
        data es un diccionario de columnas y valores a actualizar."""
        if not data:
            return False  # nada que actualizar

        columnas = []
        valores = []
        for key, value in data.items():
            columnas.append(f"{key} = %s")
            valores.append(value)
        valores.append(user_id)

        query = f"UPDATE usuarios SET {', '.join(columnas)} WHERE id = %s"

        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(valores))
                conn.commit()
                return cursor.rowcount > 0  # True si se actualizó alguna fila

    @classmethod
    def add_user(cls, email: str, nombre: str = None, activo: bool = True, tipo_suscripcion: str = 'gratuito', preferencias: dict = None):
        """Inserta un nuevo usuario en la tabla."""
        query = """
            INSERT INTO usuarios (email, nombre, activo, tipo_suscripcion, preferencias)
            VALUES (%s, %s, %s, %s, %s)
        """
        import json
        preferencias_json = json.dumps(preferencias) if preferencias else None

        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (email, nombre, activo, tipo_suscripcion, preferencias_json))
                conn.commit()
                return cursor.lastrowid  # Devuelve el ID del usuario creado

    @classmethod
    def inactivate_user(cls, user_id: int):
        """Marca un usuario como inactivo (activo = 0)"""
        query = "UPDATE usuarios SET activo = 0 WHERE id = %s"
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (user_id,))
                conn.commit()
                return cursor.rowcount > 0  # True si actualizó alguna fila