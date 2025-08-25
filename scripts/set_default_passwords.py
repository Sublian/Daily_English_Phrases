#!/usr/bin/env python3
"""
Script para asignar contraseña por defecto a usuarios sin contraseña
Contraseña por defecto: 'FraseDiaria'
"""

import sys
import os
from werkzeug.security import generate_password_hash

# =========================================================
# Lógica para agregar la ruta del proyecto al sys.path
# Esto es crucial para que las importaciones funcionen
# en cualquier subdirectorio de un servidor.
# =========================================================

# Obtiene la ruta del directorio del archivo actual (scripts/)
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# Sube un nivel para llegar a la raíz del proyecto (mysite/)
project_root = os.path.dirname(current_script_dir)

# Agrega la ruta raíz del proyecto al path de Python
sys.path.insert(0, project_root)

# =========================================================
# Ahora las importaciones absolutas funcionarán correctamente
# =========================================================
from database import DatabaseManager
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def set_default_passwords():
    """
    Asigna contraseña por defecto 'FraseDiaria' a usuarios que no tienen contraseña
    """
    default_password = 'FraseDiaria'
    password_hash = generate_password_hash(default_password)
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Buscar usuarios sin contraseña (password_hash es NULL o vacío)
            cursor.execute("""
                SELECT id, email, nombre 
                FROM usuarios 
                WHERE password_hash IS NULL OR password_hash = ''
            """)
            
            usuarios_sin_password = cursor.fetchall()
            
            if not usuarios_sin_password:
                logger.info("✅ No se encontraron usuarios sin contraseña")
                return 0
            
            logger.info(f"📋 Encontrados {len(usuarios_sin_password)} usuarios sin contraseña")
            
            # Mostrar usuarios que serán actualizados
            print("\n🔍 Usuarios que recibirán contraseña por defecto:")
            for usuario in usuarios_sin_password:
                print(f"  - ID: {usuario['id']}, Email: {usuario['email']}, Nombre: {usuario['nombre']}")
            
            # Confirmar acción
            respuesta = input(f"\n❓ ¿Desea asignar la contraseña '{default_password}' a estos {len(usuarios_sin_password)} usuarios? (s/N): ")
            
            if respuesta.lower() not in ['s', 'si', 'sí', 'y', 'yes']:
                logger.info("❌ Operación cancelada por el usuario")
                return 0
            
            # Actualizar contraseñas
            usuarios_actualizados = 0
            
            for usuario in usuarios_sin_password:
                try:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET password_hash = %s 
                        WHERE id = %s
                    """, (password_hash, usuario['id']))
                    
                    usuarios_actualizados += 1
                    logger.info(f"✅ Contraseña asignada a usuario ID: {usuario['id']} ({usuario['email']})")
                    
                except Exception as e:
                    logger.error(f"❌ Error al actualizar usuario ID {usuario['id']}: {e}")
            
            # Confirmar cambios
            conn.commit()
            
            logger.info(f"🎉 Proceso completado: {usuarios_actualizados} usuarios actualizados")
            print(f"\n✅ Se asignó contraseña por defecto a {usuarios_actualizados} usuarios")
            print(f"🔑 Contraseña asignada: '{default_password}'")
            print("📧 Los usuarios pueden cambiar su contraseña desde su perfil")
            
            return usuarios_actualizados
            
    except Exception as e:
        logger.error(f"❌ Error en el proceso: {e}")
        print(f"\n❌ Error: {e}")
        return 0

def main():
    """
    Función principal del script
    """
    print("🔐 Script para asignar contraseñas por defecto")
    print("=" * 50)
    
    try:
        usuarios_actualizados = set_default_passwords()
        
        if usuarios_actualizados > 0:
            print(f"\n🎯 Resumen:")
            print(f"   - Usuarios actualizados: {usuarios_actualizados}")
            print(f"   - Contraseña por defecto: 'FraseDiaria'")
            print(f"   - Los usuarios pueden cambiar su contraseña en su perfil")
        
    except KeyboardInterrupt:
        print("\n⚠️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        logger.error(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()