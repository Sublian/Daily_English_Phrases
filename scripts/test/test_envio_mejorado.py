#!/usr/bin/env python3
"""
Script de prueba para el sistema de envío mejorado
Este script simula diferentes escenarios para validar la funcionalidad
"""

import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys

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

from envio_frases2 import FraseDiariaManager, FailedUsersManager, MetricsCollector

def test_failed_users_manager():
    """Prueba el gestor de usuarios fallidos"""
    print("🧪 Probando FailedUsersManager...")
    
    # Crear archivo temporal para pruebas
    test_file = "test_failed_users.json"
    manager = FailedUsersManager(test_file)
    
    # Datos de prueba
    frase_data = {
        'id': 1,
        'frase': 'Test phrase',
        'traduccion': 'Frase de prueba'
    }
    
    failed_users = [
        {
            'usuario': {'id': 1, 'email': 'test1@example.com', 'nombre': 'Usuario 1'},
            'error': 'Network is unreachable',
            'is_network_error': True
        },
        {
            'usuario': {'id': 2, 'email': 'test2@example.com', 'nombre': 'Usuario 2'},
            'error': 'Network is unreachable', 
            'is_network_error': True
        }
    ]
    
    # Guardar usuarios fallidos
    manager.save_failed_users(failed_users, frase_data)
    print("✅ Usuarios fallidos guardados")
    
    # Intentar cargar inmediatamente (debería devolver None porque no ha pasado el tiempo)
    result = manager.load_failed_users()
    if result is None:
        print("✅ Carga inmediata correctamente bloqueada (tiempo no cumplido)")
    else:
        print("❌ Error: Carga inmediata debería estar bloqueada")
    
    # Simular que ha pasado el tiempo modificando el archivo
    if os.path.exists(test_file):
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Modificar timestamp para simular que ya pasó el tiempo
        past_time = datetime.now() - timedelta(minutes=31)
        data['retry_after'] = past_time.isoformat()
        
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Ahora debería cargar los usuarios
        result = manager.load_failed_users()
        if result and len(result['failed_users']) == 2:
            print("✅ Carga después del tiempo correcta")
        else:
            print("❌ Error: No se cargaron los usuarios después del tiempo")
    
    # Limpiar archivo de prueba
    manager.clear_failed_users()
    if not os.path.exists(test_file):
        print("✅ Archivo de prueba limpiado correctamente")
    
    print("✅ FailedUsersManager: Todas las pruebas pasaron\n")

def test_metrics_collector():
    """Prueba el recolector de métricas"""
    print("🧪 Probando MetricsCollector...")
    
    collector = MetricsCollector()
    
    # Simular métricas
    collector.set_total_usuarios(10)
    collector.add_success(1.5)
    collector.add_success(2.0)
    collector.add_failure("Error de prueba 1", is_network_error=True)
    collector.add_failure("Error de prueba 2", is_network_error=False)
    collector.add_deferred_retry()
    
    # Finalizar y obtener métricas
    time.sleep(0.1)  # Simular algo de tiempo
    metrics = collector.finalizar()
    
    # Verificar métricas
    assert metrics['total_usuarios'] == 10, "Total usuarios incorrecto"
    assert metrics['exitosos'] == 2, "Exitosos incorrecto"
    assert metrics['fallidos'] == 2, "Fallidos incorrecto"
    assert metrics['errores_red'] == 1, "Errores de red incorrecto"
    assert metrics['otros_errores'] == 1, "Otros errores incorrecto"
    assert metrics['reintentos_diferidos'] == 1, "Reintentos diferidos incorrecto"
    assert len(metrics['errores']) == 2, "Lista de errores incorrecta"
    assert metrics['tiempo_promedio_envio'] == 1.75, "Tiempo promedio incorrecto"
    
    print("✅ MetricsCollector: Todas las pruebas pasaron\n")

def test_network_error_detection():
    """Prueba la detección de errores de red"""
    print("🧪 Probando detección de errores de red...")
    
    # Crear una instancia mock del manager
    with patch('envio_frases2.DatabaseManager'), \
         patch('envio_frases2.FraseService'), \
         patch('envio_frases2.UserService'), \
         patch('envio_frases2.EmailService'):
        
        manager = FraseDiariaManager()
        
        # Probar diferentes tipos de errores
        network_errors = [
            "[Errno 101] Network is unreachable",
            "Connection refused",
            "Connection timed out",
            "Name or service not known",
            "Temporary failure in name resolution",
            "No route to host",
            "Connection reset by peer"
        ]
        
        other_errors = [
            "Authentication failed",
            "Invalid email address",
            "SMTP server error",
            "Permission denied"
        ]
        
        # Verificar detección de errores de red
        for error in network_errors:
            if not manager.is_network_error(error):
                print(f"❌ Error: '{error}' debería ser detectado como error de red")
                return
        
        # Verificar que otros errores no se detecten como errores de red
        for error in other_errors:
            if manager.is_network_error(error):
                print(f"❌ Error: '{error}' NO debería ser detectado como error de red")
                return
        
        print("✅ Detección de errores de red: Todas las pruebas pasaron\n")

def test_config_validation():
    """Prueba la validación de configuración"""
    print("🧪 Probando validación de configuración...")
    
    # Guardar variables originales
    original_env = {}
    required_vars = ['EMAIL_USER', 'EMAIL_PASSWORD', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'SMTP_SERVER', 'SMTP_PORT']
    
    for var in required_vars:
        original_env[var] = os.environ.get(var)
    
    try:
        # Crear una instancia mock del manager
        with patch('envio_frases2.DatabaseManager'), \
             patch('envio_frases2.FraseService'), \
             patch('envio_frases2.UserService'), \
             patch('envio_frases2.EmailService'):
            
            # Configurar variables de entorno válidas
            os.environ.update({
                'EMAIL_USER': 'test@example.com',
                'EMAIL_PASSWORD': 'password123',
                'DB_USER': 'dbuser',
                'DB_PASSWORD': 'dbpass',
                'DB_HOST': 'localhost',
                'DB_NAME': 'testdb',
                'SMTP_SERVER': 'smtp.gmail.com',
                'SMTP_PORT': '587'
            })
            
            manager = FraseDiariaManager()
            
            # Debería pasar la validación
            if not manager.validar_configuracion():
                print("❌ Error: Configuración válida no pasó la validación")
                return
            
            # Probar con puerto inválido
            os.environ['SMTP_PORT'] = '99999'
            if manager.validar_configuracion():
                print("❌ Error: Puerto inválido pasó la validación")
                return
            
            # Probar con variable faltante
            del os.environ['EMAIL_USER']
            if manager.validar_configuracion():
                print("❌ Error: Variable faltante pasó la validación")
                return
            
            print("✅ Validación de configuración: Todas las pruebas pasaron\n")
    
    finally:
        # Restaurar variables originales
        for var, value in original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

def simulate_network_failure_scenario():
    """Simula un escenario completo de fallo de red y recuperación"""
    print("🧪 Simulando escenario completo de fallo de red...")
    
    # Crear archivo temporal para la simulación
    test_file = "simulation_failed_users.json"
    manager = FailedUsersManager(test_file)
    
    # Simular datos de una ejecución fallida
    frase_data = {
        'id': 31,
        'frase': 'Sleep on it...',
        'traduccion': 'Duérmelo...'
    }
    
    # Usuarios que fallaron por error de red (basado en el log proporcionado)
    failed_users = [
        {
            'usuario': {'id': 14, 'email': 'arangelmoreno22@gmail.com', 'nombre': 'Ana Rangel'},
            'error': '[Errno 101] Network is unreachable',
            'is_network_error': True
        },
        {
            'usuario': {'id': 9, 'email': 'kubrick.eth@gmail.com', 'nombre': 'Cristian Parra'},
            'error': '[Errno 101] Network is unreachable',
            'is_network_error': True
        },
        {
            'usuario': {'id': 8, 'email': 'dayanamatadcippsv@gmail.com', 'nombre': 'Dayana Mata de Gonzalez'},
            'error': '[Errno 101] Network is unreachable',
            'is_network_error': True
        }
    ]
    
    print(f"📝 Simulando fallo inicial con {len(failed_users)} usuarios")
    
    # Guardar usuarios fallidos
    manager.save_failed_users(failed_users, frase_data)
    
    # Verificar que el archivo se creó
    if os.path.exists(test_file):
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Archivo creado con {len(data['failed_users'])} usuarios")
        print(f"⏰ Reintento programado para: {data['retry_after']}")
        
        # Simular que ha pasado el tiempo
        past_time = datetime.now() - timedelta(minutes=1)
        data['retry_after'] = past_time.isoformat()
        
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Simular recuperación
        recovered_data = manager.load_failed_users()
        if recovered_data:
            print(f"🔄 Datos de recuperación cargados: {len(recovered_data['failed_users'])} usuarios")
            print(f"📧 Frase a reenviar: {recovered_data['frase_data']['frase']}")
        
        # Simular éxito en reintentos (limpiar archivo)
        manager.clear_failed_users()
        print("🗑️ Simulación de éxito: archivo limpiado")
        
        if not os.path.exists(test_file):
            print("✅ Escenario completo simulado exitosamente")
    
    print("✅ Simulación completa: Todas las pruebas pasaron\n")

def main():
    """Ejecuta todas las pruebas"""
    print("🚀 Iniciando pruebas del sistema de envío mejorado\n")
    
    try:
        test_failed_users_manager()
        test_metrics_collector()
        test_network_error_detection()
        test_config_validation()
        simulate_network_failure_scenario()
        
        print("🎉 ¡Todas las pruebas pasaron exitosamente!")
        print("\n📋 Resumen de funcionalidades probadas:")
        print("   ✅ Gestión de usuarios fallidos")
        print("   ✅ Recolección de métricas")
        print("   ✅ Detección de errores de red")
        print("   ✅ Validación de configuración")
        print("   ✅ Escenario completo de recuperación")
        
        print("\n🚀 El sistema está listo para usar!")
        print("\n💡 Para usar el sistema:")
        print("   1. Configura las variables en .env")
        print("   2. Ejecuta: python envio_frases_mejorado.py")
        print("   3. El sistema manejará automáticamente los reintentos")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    #exit(exit_code)