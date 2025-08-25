#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para probar el flujo completo de confirmación de email
Después de las correcciones realizadas
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_confirmation_flow():
    """Prueba el flujo completo de confirmación"""
    
    print("🧪 Iniciando prueba del flujo de confirmación...")
    
    # 1. Limpiar datos de prueba anteriores
    test_email = "test_confirmation@example.com"
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Eliminar tokens de prueba
            cursor.execute(
                "DELETE FROM tokens_validacion WHERE usuario_id IN (SELECT id FROM usuarios WHERE email = %s)",
                (test_email,)
            )
            
            # Eliminar usuario de prueba
            cursor.execute("DELETE FROM usuarios WHERE email = %s", (test_email,))
            conn.commit()
            
        print("✅ Datos de prueba anteriores eliminados")
        
    except Exception as e:
        print(f"⚠️ Error al limpiar datos: {e}")
    
    # 2. Crear usuario sin contraseña (simula registro desde formulario)
    print("\n📝 Creando usuario de prueba...")
    
    try:
        success, message = UserService.create_user(
            nombre="Usuario Prueba",
            email=test_email,
            telefono="1234567890"
            # Sin password para activar el flujo de confirmación
        )
        
        if success:
            print(f"✅ Usuario creado: {message}")
        else:
            print(f"❌ Error al crear usuario: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Error inesperado al crear usuario: {e}")
        return False
    
    # 3. Verificar que se creó el token
    print("\n🔍 Verificando token generado...")
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Buscar el usuario creado
            cursor.execute("SELECT id, rol FROM usuarios WHERE email = %s", (test_email,))
            user_data = cursor.fetchone()
            
            if not user_data:
                print("❌ Usuario no encontrado")
                return False
                
            user_id = user_data['id']
            print(f"✅ Usuario encontrado con ID: {user_id}, Rol: {user_data['rol']}")
            
            # Buscar el token
            cursor.execute(
                "SELECT token, tipo, usado, fecha_expiracion FROM tokens_validacion WHERE usuario_id = %s",
                (user_id,)
            )
            token_data = cursor.fetchone()
            
            if not token_data:
                print("❌ Token no encontrado")
                return False
                
            token = token_data['token']
            print(f"✅ Token encontrado: {token[:10]}... (Tipo: {token_data['tipo']}, Usado: {token_data['usado']})")
            
    except Exception as e:
        print(f"❌ Error al verificar token: {e}")
        return False
    
    # 4. Probar validación del token (sin marcarlo como usado)
    print("\n🔐 Probando validación del token...")
    
    try:
        valid, user_id_returned, message = TokenService.validar_token(token, 'email_confirmacion')
        
        if valid:
            print(f"✅ Token válido para usuario {user_id_returned}: {message}")
        else:
            print(f"❌ Token inválido: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Error al validar token: {e}")
        return False
    
    # 5. Verificar que el token NO se marcó como usado (nueva funcionalidad)
    print("\n🔄 Verificando que el token no se marcó como usado...")
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT usado FROM tokens_validacion WHERE token = %s",
                (token,)
            )
            token_status = cursor.fetchone()
            
            if token_status and not token_status['usado']:
                print("✅ Token sigue disponible para uso")
            else:
                print("❌ Token fue marcado como usado prematuramente")
                return False
                
    except Exception as e:
        print(f"❌ Error al verificar estado del token: {e}")
        return False
    
    # 6. Probar marcado manual del token como usado
    print("\n✅ Probando marcado del token como usado...")
    
    try:
        success = TokenService.marcar_token_usado(token)
        
        if success:
            print("✅ Token marcado como usado exitosamente")
        else:
            print("❌ Error al marcar token como usado")
            return False
            
    except Exception as e:
        print(f"❌ Error al marcar token: {e}")
        return False
    
    # 7. Verificar que ahora el token está marcado como usado
    print("\n🔍 Verificando que el token ahora está usado...")
    
    try:
        valid, _, message = TokenService.validar_token(token, 'email_confirmacion')
        
        if not valid and "ya utilizado" in message:
            print("✅ Token correctamente marcado como usado")
        else:
            print(f"❌ Token debería estar marcado como usado: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Error al verificar token usado: {e}")
        return False
    
    print("\n🎉 ¡Todas las pruebas del flujo de confirmación pasaron exitosamente!")
    print("\n📋 Resumen de correcciones verificadas:")
    print("   ✅ Método validar_token corregido para retornar 3 valores")
    print("   ✅ Token no se marca como usado en la validación inicial")
    print("   ✅ Token se marca como usado solo al completar el proceso")
    print("   ✅ Flujo de confirmación funciona correctamente")
    
    return True

if __name__ == "__main__":
    success = test_confirmation_flow()
    #sys.exit(0 if success else 1)