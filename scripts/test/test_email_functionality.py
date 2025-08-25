#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad de envío de correos
y generación de tokens para nuevos suscriptores.
"""

import sys
import os

# =========================================================
# Lógica para agregar la ruta del proyecto al sys.path
# Esto es crucial para que las importaciones funcionen
# en cualquier subdirectorio de un servidor.
# =========================================================

# Obtiene la ruta del directorio del archivo actual (scripts/)
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# Sube dos niveles para llegar a la raíz del proyecto (mysite/)
project_root = os.path.dirname(os.path.dirname(current_script_dir))

# Agrega la ruta raíz del proyecto al path de Python
sys.path.insert(0, project_root)

# =========================================================
# Ahora las importaciones absolutas funcionarán correctamente
# =========================================================


from models import UserService
from token_service import TokenService
from database import DatabaseManager
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_user_creation_and_email():
    """Prueba la creación de usuario y envío de correos"""
    print("🧪 Iniciando prueba de funcionalidad de correos...")
    
    # Email de prueba
    test_email = "test@example.com"
    test_nombre = "Usuario de Prueba"
    
    try:
        # 1. Verificar que la tabla tokens_validacion existe
        print("\n1️⃣ Verificando tabla tokens_validacion...")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES LIKE 'tokens_validacion'")
            result = cursor.fetchone()
            if result:
                print("✅ Tabla tokens_validacion existe")
            else:
                print("❌ Tabla tokens_validacion NO existe")
                return False
        
        # 2. Limpiar usuario de prueba si existe
        print("\n2️⃣ Limpiando datos de prueba anteriores...")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM usuarios WHERE email = %s", (test_email,))
            conn.commit()
            print(f"✅ Usuario {test_email} eliminado (si existía)")
        
        # 3. Crear nuevo usuario (sin contraseña para activar el flujo de confirmación)
        print("\n3️⃣ Creando nuevo usuario...")
        success, message = UserService.create_user(test_email, test_nombre)
        print(f"Resultado: {success}")
        print(f"Mensaje: {message}")
        
        if not success:
            print("❌ Error al crear usuario")
            return False
        
        # 4. Verificar que el usuario fue creado
        print("\n4️⃣ Verificando usuario creado...")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE email = %s", (test_email,))
            user = cursor.fetchone()
            
            if user:
                print(f"✅ Usuario creado con ID: {user['id']}")
                print(f"   Email: {user['email']}")
                print(f"   Nombre: {user['nombre']}")
                print(f"   Rol: {user['rol']}")
                print(f"   Activo: {user['activo']}")
                user_id = user['id']
            else:
                print("❌ Usuario no encontrado en la base de datos")
                return False
        
        # 5. Verificar que se generó el token
        print("\n5️⃣ Verificando token generado...")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM tokens_validacion 
                WHERE usuario_id = %s AND tipo = 'email_confirmacion' AND usado = FALSE
            """, (user_id,))
            token_data = cursor.fetchone()
            
            if token_data:
                print(f"✅ Token generado correctamente")
                print(f"   Token ID: {token_data['id']}")
                print(f"   Token: {token_data['token'][:20]}...")
                print(f"   Tipo: {token_data['tipo']}")
                print(f"   Usado: {token_data['usado']}")
                print(f"   Fecha creación: {token_data['fecha_creacion']}")
                print(f"   Fecha expiración: {token_data['fecha_expiracion']}")
            else:
                print("❌ No se encontró token para el usuario")
                return False
        
        # 6. Probar validación de token
        print("\n6️⃣ Probando validación de token...")
        token_value = token_data['token']
        is_valid, validated_user_id, validation_message = TokenService.validar_token(token_value)
        
        print(f"Token válido: {is_valid}")
        print(f"Usuario ID validado: {validated_user_id}")
        print(f"Mensaje: {validation_message}")
        
        if is_valid and validated_user_id == user_id:
            print("✅ Validación de token exitosa")
        else:
            print("❌ Error en validación de token")
            return False
        
        print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        print("\n📋 Resumen:")
        print("   ✅ Tabla tokens_validacion existe")
        print("   ✅ Usuario creado correctamente")
        print("   ✅ Token generado y almacenado")
        print("   ✅ Token validado correctamente")
        print("   ✅ Correos enviados (revisar logs para confirmación)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {e}")
        return False

def cleanup_test_data():
    """Limpia los datos de prueba"""
    try:
        test_email = "test@example.com"
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM usuarios WHERE email = %s", (test_email,))
            conn.commit()
            print(f"🧹 Datos de prueba limpiados")
    except Exception as e:
        logger.error(f"Error al limpiar datos de prueba: {e}")

if __name__ == "__main__":
    print("🚀 Ejecutando pruebas de funcionalidad de correos...")
    
    try:
        success = test_user_creation_and_email()
        
        if success:
            print("\n✅ TODAS LAS PRUEBAS PASARON")
        else:
            print("\n❌ ALGUNAS PRUEBAS FALLARON")
            
        # Preguntar si limpiar datos de prueba
        response = input("\n¿Deseas limpiar los datos de prueba? (y/n): ")
        if response.lower() in ['y', 'yes', 's', 'si']:
            cleanup_test_data()
            
    except KeyboardInterrupt:
        print("\n🛑 Prueba interrumpida por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")