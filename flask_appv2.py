import os
import mysql.connector
from flask import Flask, jsonify, render_template_string, request, redirect, url_for, flash
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import logging
import re
from werkzeug.security import generate_password_hash

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación Flask
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tu-clave-secreta-aqui')

# Configuración de base de datos
DB_CONFIG = {
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4',
    'autocommit': True
}

# Zona horaria local
LOCAL_TZ = timezone(timedelta(hours=-5))

def get_db_connection():
    """Obtiene conexión a la base de datos"""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        logger.error(f"Error de conexión: {err}")
        return None

def validar_email(email):
    """Valida formato de email"""
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

def get_estadisticas():
    """Obtiene estadísticas de los envíos"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
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
                'total_frases': total_frases,
                'fecha_consulta': datetime.now(LOCAL_TZ).strftime('%d/%m/%Y %H:%M:%S')
            }
    finally:
        conn.close()

def get_usuarios():
    """Obtiene lista de usuarios"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT u.*, 
                       COUNT(te.id) as total_envios,
                       MAX(te.enviado_en) as ultimo_envio
                FROM usuarios u
                LEFT JOIN trazabilidad_envio te ON u.id = te.usuario_id
                GROUP BY u.id
                ORDER BY u.fecha_registro DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()

def agregar_usuario(email, nombre=None):
    """Agrega un nuevo usuario"""
    if not validar_email(email):
        return False, "Email inválido"
    
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión a la base de datos"
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (email, nombre, activo, tipo_suscripcion) 
                VALUES (%s, %s, TRUE, 'gratuito')
            """, (email, nombre))
            conn.commit()
            return True, "Usuario agregado exitosamente"
    except mysql.connector.IntegrityError:
        return False, "El email ya está registrado"
    except mysql.connector.Error as err:
        logger.error(f"Error al agregar usuario: {err}")
        return False, "Error al agregar usuario"
    finally:
        conn.close()

def actualizar_usuario(user_id, activo=None, tipo_suscripcion=None):
    """Actualiza un usuario"""
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión"
    
    try:
        with conn.cursor() as cursor:
            updates = []
            params = []
            
            if activo is not None:
                updates.append("activo = %s")
                params.append(activo)
            
            if tipo_suscripcion is not None:
                updates.append("tipo_suscripcion = %s")
                params.append(tipo_suscripcion)
            
            if not updates:
                return False, "No hay cambios para actualizar"
            
            params.append(user_id)
            query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
            
            cursor.execute(query, params)
            conn.commit()
            return True, "Usuario actualizado exitosamente"
    except mysql.connector.Error as err:
        logger.error(f"Error al actualizar usuario: {err}")
        return False, "Error al actualizar usuario"
    finally:
        conn.close()

# Template HTML mejorado
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Frases Diarias</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .nav-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .nav-tab {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            text-decoration: none;
            font-size: 1rem;
        }
        
        .nav-tab:hover, .nav-tab.active {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .stat-label {
            color: #666;
            font-size: 1.1rem;
        }
        
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .info { color: #17a2b8; }
        .primary { color: #667eea; }
        .purple { color: #764ba2; }
        
        .section {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #333;
        }
        
        .form-control {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5a6fd8;
            transform: translateY(-2px);
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background: #218838;
        }
        
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        
        .btn-danger:hover {
            background: #c82333;
        }
        
        .btn-sm {
            padding: 6px 12px;
            font-size: 0.875rem;
        }
        
        .table-responsive {
            overflow-x: auto;
        }
        
        .table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        .table th,
        .table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        
        .table th {
            background: #f8f9fa;
            font-weight: bold;
            color: #495057;
        }
        
        .table tbody tr:hover {
            background: #f8f9fa;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .badge-success {
            background: #d4edda;
            color: #155724;
        }
        
        .badge-danger {
            background: #f8d7da;
            color: #721c24;
        }
        
        .badge-warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .badge-info {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        .alert {
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            border: 1px solid transparent;
        }
        
        .alert-success {
            background: #d4edda;
            border-color: #c3e6cb;
            color: #155724;
        }
        
        .alert-danger {
            background: #f8d7da;
            border-color: #f5c6cb;
            color: #721c24;
        }
        
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            opacity: 0.8;
        }
        
        .social-links {
            margin: 15px 0;
        }
        
        .social-links a {
            display: inline-block;
            margin: 0 15px;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .social-links a:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }
            
            .nav-tabs {
                flex-direction: column;
                align-items: center;
            }
            
            .table-responsive {
                font-size: 0.875rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Dashboard Frases Diarias</h1>
            <p>Sistema de gestión automático</p>
        </div>
        
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchTab('dashboard')">
                <i class="fas fa-chart-dashboard"></i> Dashboard
            </button>
            <button class="nav-tab" onclick="switchTab('usuarios')">
                <i class="fas fa-users"></i> Usuarios
            </button>
            <button class="nav-tab" onclick="switchTab('suscripcion')">
                <i class="fas fa-user-plus"></i> Suscribirse
            </button>
        </div>
        
        <!-- Tab Dashboard -->
        <div id="dashboard" class="tab-content active">
            {% if stats %}
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number primary">{{ stats.total_envios }}</div>
                    <div class="stat-label">Total Enviados</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number success">{{ stats.envios_exitosos }}</div>
                    <div class="stat-label">Envíos Exitosos</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number purple">{{ stats.total_usuarios }}</div>
                    <div class="stat-label">Total Usuarios</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number info">{{ stats.usuarios_activos }}</div>
                    <div class="stat-label">Usuarios Activos</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number warning">{{ stats.tasa_exito }}%</div>
                    <div class="stat-label">Tasa de Éxito</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-number info">{{ stats.total_frases }}</div>
                    <div class="stat-label">Frases Disponibles</div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📧 Último Envío</h2>
                {% if stats.ultimo_envio %}
                <div style="background: #f8f9fa; border-radius: 10px; padding: 20px;">
                    <span class="badge {% if stats.ultimo_envio.resultado == 'exito' %}badge-success{% else %}badge-danger{% endif %}">
                        {% if stats.ultimo_envio.resultado == 'exito' %}✅ EXITOSO{% else %}❌ ERROR{% endif %}
                    </span>
                    <p style="margin: 10px 0;"><strong>Fecha:</strong> {{ stats.ultimo_envio.enviado_en.strftime('%d/%m/%Y %H:%M:%S') }}</p>
                    <p style="margin: 10px 0;"><strong>Usuario:</strong> {{ stats.ultimo_envio.nombre or stats.ultimo_envio.email }}</p>
                    <p style="margin: 10px 0;"><strong>Frase:</strong> "{{ stats.ultimo_envio.frase[:100] }}{% if stats.ultimo_envio.frase|length > 100 %}...{% endif %}"</p>
                </div>
                {% else %}
                <p>No hay envíos registrados</p>
                {% endif %}
            </div>
            
            <div class="section">
                <h2 class="section-title">📈 Actividad Reciente (7 días)</h2>
                {% if stats.envios_recientes %}
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Total</th>
                                <th>Exitosos</th>
                                <th>Tasa</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for envio in stats.envios_recientes %}
                            <tr>
                                <td>{{ envio.fecha.strftime('%d/%m/%Y') }}</td>
                                <td>{{ envio.total }}</td>
                                <td>{{ envio.exitosos }}</td>
                                <td>
                                    <span class="badge {% if (envio.exitosos / envio.total * 100) >= 90 %}badge-success{% elif (envio.exitosos / envio.total * 100) >= 70 %}badge-warning{% else %}badge-danger{% endif %}">
                                        {{ (envio.exitosos / envio.total * 100) | round(1) }}%
                                    </span>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                <p>No hay actividad reciente</p>
                {% endif %}
            </div>
            {% endif %}
        </div>
        
        <!-- Tab Usuarios -->
        <div id="usuarios" class="tab-content">
            <div class="section">
                <h2 class="section-title">👥 Gestión de Usuarios</h2>
                
                {% if usuarios %}
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Email</th>
                                <th>Nombre</th>
                                <th>Estado</th>
                                <th>Suscripción</th>
                                <th>Registro</th>
                                <th>Envíos</th>
                                <th>Último Envío</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for usuario in usuarios %}
                            <tr>
                                <td>{{ usuario.email }}</td>
                                <td>{{ usuario.nombre or '-' }}</td>
                                <td>
                                    <span class="badge {% if usuario.activo %}badge-success{% else %}badge-danger{% endif %}">
                                        {% if usuario.activo %}Activo{% else %}Inactivo{% endif %}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge {% if usuario.tipo_suscripcion == 'premium' %}badge-warning{% else %}badge-info{% endif %}">
                                        {{ usuario.tipo_suscripcion.title() }}
                                    </span>
                                </td>
                                <td>{{ usuario.fecha_registro.strftime('%d/%m/%Y') }}</td>
                                <td>{{ usuario.total_envios or 0 }}</td>
                                <td>{{ usuario.ultimo_envio.strftime('%d/%m/%Y') if usuario.ultimo_envio else '-' }}</td>
                                <td>
                                    <form method="POST" action="/actualizar_usuario" style="display: inline;">
                                        <input type="hidden" name="user_id" value="{{ usuario.id }}">
                                        <input type="hidden" name="activo" value="{% if usuario.activo %}0{% else %}1{% endif %}">
                                        <button type="submit" class="btn btn-sm {% if usuario.activo %}btn-danger{% else %}btn-success{% endif %}">
                                            {% if usuario.activo %}Desactivar{% else %}Activar{% endif %}
                                        </button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                <p>No hay usuarios registrados.</p>
                {% endif %}
            </div>
        </div>
        
        <!-- Tab Suscripción -->
        <div id="suscripcion" class="tab-content">
            <div class="section">
                <h2 class="section-title">✉️ Nuevo Suscriptor</h2>
                
                <!-- Mostrar mensajes -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert {% if category == 'success' %}alert-success{% else %}alert-danger{% endif %}">
                                {{ message }}
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                <form method="POST" action="/agregar_usuario">
                    <div class="form-group">
                        <label for="email">Email *</label>
                        <input type="email" id="email" name="email" class="form-control" required 
                               placeholder="ejemplo@correo.com">
                    </div>
                    
                    <div class="form-group">
                        <label for="nombre">Nombre (opcional)</label>
                        <input type="text" id="nombre" name="nombre" class="form-control" 
                               placeholder="Tu nombre completo">
                    </div>
                    
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-user-plus"></i> Agregar Suscriptor
                    </button>
                </form>
                
                <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                    <h3 style="color: #667eea; margin-bottom: 15px;">ℹ️ Información</h3>
                    <ul style="color: #666; line-height: 1.6;">
                        <li>Los nuevos suscriptores se registran como usuarios gratuitos</li>
                        <li>Recibirán automáticamente la frase diaria por email</li>
                        <li>Pueden gestionar su suscripción desde el panel de administración</li>
                        <li>El sistema valida automáticamente el formato del email</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <button class="btn btn-success" onclick="window.location.reload()">
                <i class="fas fa-sync-alt"></i> Actualizar Datos
            </button>
        </div>
        
        <div class="footer">
            <div class="social-links">
                <a href="https://linkedin.com/in/luisangelgp" target="_blank" rel="noopener noreferrer">
                    <i class="fab fa-linkedin"></i>LinkedIn
                </a>
                <a href="https://github.com/Sublian" target="_blank" rel="noopener noreferrer">
                    <i class="fab fa-github"></i>GitHub
                </a>
            </div>
            <p>📅 Última actualización: {{ stats.fecha_consulta if stats else 'N/A' }}</p>
            <p>🤖 Sistema automático de frases diarias</p>
            <p style="margin-top: 10px; font-size: 0.9rem; opacity: 0.7;">
                Desarrollado con ❤️ usando Python & Flask
            </p>
        </div>
    </div>
    
    <script>
        function switchTab(tabName) {
            // Ocultar todos los contenidos de tabs
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(tab => tab.classList.remove('active'));
            
            // Remover clase active de todos los tabs
            const tabButtons = document.querySelectorAll('.nav-tab');
            tabButtons.forEach(tab => tab.classList.remove('active'));
            
            // Mostrar el tab seleccionado
            document.getElementById(tabName).classList.add('active');
            
            // Agregar clase active al botón clickeado
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Página principal del dashboard"""
    stats = get_estadisticas()
    usuarios = get_usuarios()
    return render_template_string(HTML_TEMPLATE, stats=stats, usuarios=usuarios)

@app.route('/agregar_usuario', methods=['POST'])
def agregar_usuario_route():
    """Endpoint para agregar nuevo usuario"""
    email = request.form.get('email', '').strip()
    nombre = request.form.get('nombre', '').strip() or None
    
    if not email:
        flash('El email es requerido', 'error')
        return redirect(url_for('dashboard') + '#suscripcion')
    
    success, message = agregar_usuario(email, nombre)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('dashboard') + '#suscripcion')

@app.route('/actualizar_usuario', methods=['POST'])
def actualizar_usuario_route():
    """Endpoint para actualizar usuario"""
    user_id = request.form.get('user_id')
    activo = request.form.get('activo') == '1'
    tipo_suscripcion = request.form.get('tipo_suscripcion')
    
    if not user_id:
        flash('ID de usuario requerido', 'error')
        return redirect(url_for('dashboard') + '#usuarios')
    
    success, message = actualizar_usuario(user_id, activo=activo, tipo_suscripcion=tipo_suscripcion)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('dashboard') + '#usuarios')
    
@app.route('/api/stats')
def api_stats():
    """API endpoint para obtener estadísticas en JSON"""
    stats = get_estadisticas()
    if stats:
        # Convertir datetime a string para JSON
        if stats['ultimo_envio'] and stats['ultimo_envio']['enviado_en']:
            stats['ultimo_envio']['enviado_en'] = stats['ultimo_envio']['enviado_en'].strftime('%Y-%m-%d %H:%M:%S')
        
        for envio in stats['envios_recientes']:
            envio['fecha'] = envio['fecha'].strftime('%Y-%m-%d')
        
        return jsonify(stats)
    else:
        return jsonify({'error': 'No se pudieron obtener las estadísticas'}), 500

@app.route('/health')
def health_check():
    """Endpoint para verificar que el servicio está funcionando"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now(LOCAL_TZ).isoformat(),
        'service': 'Frases Diarias Dashboard'
    })

if __name__ == '__main__':
    app.run(debug=True)