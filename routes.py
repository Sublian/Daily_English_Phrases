from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import UserService, StatsService
from auth import admin_required
from config import Config
from database import DatabaseManager

# Crear blueprint para las rutas
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    """Página principal del dashboard"""
    stats = StatsService.get_dashboard_stats()
    usuarios = UserService.get_all_users() if current_user.is_authenticated and current_user.is_admin else None
    user_stats = None
    
    # Obtener estadísticas específicas del usuario si está autenticado y no es admin
    if current_user.is_authenticated and not current_user.is_admin:
        user_stats = StatsService.get_user_stats(current_user.id)
    
    return render_template(
        'dashboard.html',
        stats=stats,
        usuarios=usuarios,
        user_stats=user_stats
    )

@main_bp.route('/agregar_usuario', methods=['POST'])
def agregar_usuario_route():
    """Endpoint para agregar nuevo usuario"""
    email = request.form.get('email', '').strip()
    nombre = request.form.get('nombre', '').strip() or None
    password = request.form.get('password', '').strip() or None

    if not email:
        flash('El email es requerido', 'error')
        return redirect(url_for('main.dashboard') + '#suscripcion')

    # Crear usuario y enviar correo de confirmación usando método estático
    success, message = UserService.create_user(email, nombre, password)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('main.dashboard') + '#suscripcion')

@main_bp.route('/confirmar-email/<token>', methods=['GET', 'POST'])
def confirmar_email(token):
    """Endpoint para confirmar email con token y establecer contraseña"""
    from token_service import TokenService
    from werkzeug.security import generate_password_hash
    
    # Validar token
    valid, user_id, message = TokenService.validar_token(token, 'email_confirmacion')
    
    if not valid:
        flash(f'Token inválido o expirado: {message}', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Obtener información del usuario
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT email, nombre FROM usuarios WHERE id = %s', (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                flash('Usuario no encontrado', 'error')
                return redirect(url_for('main.dashboard'))
    except Exception as e:
        flash(f'Error al obtener datos del usuario: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validaciones
        if not password or len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('establecer_password.html', 
                                 token=token, 
                                 email=user_data['email'], 
                                 nombre=user_data['nombre'])
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('establecer_password.html', 
                                 token=token, 
                                 email=user_data['email'], 
                                 nombre=user_data['nombre'])
        
        try:
            # Encriptar contraseña y actualizar usuario
            password_hash = generate_password_hash(password)
            
            with DatabaseManager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE usuarios SET password_hash = %s, rol = %s WHERE id = %s',
                    (password_hash, 'usuario', user_id)
                )
                conn.commit()
            
            # Marcar token como usado
            TokenService.marcar_token_usado(token)
            
            flash('¡Cuenta activada exitosamente! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'Error al establecer contraseña: {str(e)}', 'error')
            return render_template('establecer_password.html', 
                                 token=token, 
                                 email=user_data['email'], 
                                 nombre=user_data['nombre'])
    
    # GET request - mostrar formulario
    return render_template('establecer_password.html', 
                         token=token, 
                         email=user_data['email'], 
                         nombre=user_data['nombre'])

@main_bp.route('/actualizar_usuario', methods=['POST'])
@login_required
@admin_required
def actualizar_usuario_route():
    """Endpoint para actualizar usuario (solo admin)"""
    user_id = request.form.get('user_id')
    activo = request.form.get('activo') == '1'
    tipo_suscripcion = request.form.get('tipo_suscripcion')

    if not user_id:
        flash('ID de usuario requerido', 'error')
        return redirect(url_for('main.dashboard') + '#usuarios')

    # Actualizar usuario usando método estático
    success, message = UserService.update_user(user_id, activo=activo, tipo_suscripcion=tipo_suscripcion)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('main.dashboard') + '#usuarios')

@main_bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    """Vista de gestión de usuarios para administradores"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('search', '')
    estado = request.args.get('estado', '')
    tipo_suscripcion = request.args.get('tipo_suscripcion', '')
    rol = request.args.get('rol', '')

    # Construir la consulta base
    query = 'SELECT * FROM usuarios WHERE 1=1'
    params = []

    # Aplicar filtros
    if search:
        query += ' AND (nombre LIKE %s OR email LIKE %s)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param])

    if estado:
        query += ' AND activo = %s'
        params.append(estado == 'activo')

    if tipo_suscripcion:
        query += ' AND tipo_suscripcion = %s'
        params.append(tipo_suscripcion)

    if rol:
        query += ' AND rol = %s'
        params.append(rol)

    # Obtener total de registros para paginación
    with DatabaseManager.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        count_query = query.replace('*', 'COUNT(*) as total')
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']

        # Agregar paginación
        query += ' ORDER BY id DESC LIMIT %s OFFSET %s'
        params.extend([per_page, (page - 1) * per_page])

        # Obtener usuarios
        cursor.execute(query, params)
        usuarios = cursor.fetchall()

    total_pages = (total + per_page - 1) // per_page

    return render_template('usuarios.html',
                         usuarios=usuarios,
                         page=page,
                         total_pages=total_pages)

@main_bp.route('/usuarios/<int:id>/toggle-estado', methods=['POST'])
@login_required
@admin_required
def toggle_estado_usuario(id):
    """Cambiar estado de usuario (activo/inactivo)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Obtener estado actual
            cursor.execute('SELECT activo FROM usuarios WHERE id = %s', (id,))
            usuario = cursor.fetchone()
            
            if not usuario:
                return jsonify({'success': False, 'message': 'Usuario no encontrado'})
            
            # Cambiar estado
            nuevo_estado = not usuario['activo']
            cursor.execute('UPDATE usuarios SET activo = %s WHERE id = %s', (nuevo_estado, id))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Estado actualizado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    flash(message, 'success' if success else 'error')
    return redirect(url_for('main.dashboard') + '#usuarios')

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_route():
    """Ruta para el perfil de usuario"""
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        if nombre and nombre != current_user.nombre:
            success, message = UserService.update_user_profile(current_user.id, nombre=nombre)
            flash(message, 'success' if success else 'error')

        if current_password and new_password:
            success, message = UserService.update_user_password(
                current_user.id,
                current_password,
                new_password
            )
            flash(message, 'success' if success else 'error')

    return render_template('profile.html')

@main_bp.route('/usuarios/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_usuario(id):
    """Obtener información de un usuario específico"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM usuarios WHERE id = %s', (id,))
            usuario = cursor.fetchone()
            
            if not usuario:
                return jsonify({'success': False, 'message': 'Usuario no encontrado'})
            
            return jsonify({'success': True, 'usuario': usuario})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/usuarios/guardar', methods=['POST'])
@login_required
@admin_required
def guardar_usuario():
    """Guardar o actualizar información de usuario"""
    try:
        data = request.form
        user_id = data.get('id')
        email = data.get('email')
        nombre = data.get('nombre')
        password = data.get('password')
        tipo_suscripcion = data.get('tipo_suscripcion')
        activo = data.get('activo') == 'on'

        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            if user_id:  # Actualizar usuario existente
                update_fields = ['nombre = %s', 'email = %s', 'tipo_suscripcion = %s', 'activo = %s']
                params = [nombre, email, tipo_suscripcion, activo]
                
                if password:  # Solo actualizar contraseña si se proporciona una nueva
                    update_fields.append('password_hash = %s')
                    params.append(UserService.hash_password(password))
                
                params.append(int(user_id))
                query = f"UPDATE usuarios SET {', '.join(update_fields)} WHERE id = %s"
                cursor.execute(query, params)
                message = 'Usuario actualizado correctamente'
            else:  # Crear nuevo usuario
                if not password:
                    return jsonify({'success': False, 'message': 'La contraseña es requerida para nuevos usuarios'})
                
                cursor.execute(
                    'INSERT INTO usuarios (email, nombre, password_hash, tipo_suscripcion, activo) VALUES (%s, %s, %s, %s, %s)',
                    (email, nombre, UserService.hash_password(password), tipo_suscripcion, activo)
                )
                message = 'Usuario creado correctamente'
            
            conn.commit()
            return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/stats/envios-por-dia')
@login_required
@admin_required
def get_envios_por_dia():
    """Endpoint para obtener estadísticas de envíos por día (solo admin)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT 
                    DATE_FORMAT(CONVERT_TZ(enviado_en, '+00:00', '-05:00'), '%a') as dia,
                    COUNT(*) as total_envios
                FROM trazabilidad_envio
                WHERE enviado_en >= DATE_SUB(CONVERT_TZ(NOW(), '+00:00', '-05:00'), INTERVAL 7 DAY)
                GROUP BY DATE_FORMAT(CONVERT_TZ(enviado_en, '+00:00', '-05:00'), '%a')
                ORDER BY enviado_en
            """
            cursor.execute(query)
            resultados = cursor.fetchall()
            
            # Formatear datos para la gráfica
            dias = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']
            datos = [0] * 7
            for resultado in resultados:
                try:
                    indice = dias.index(resultado['dia'])
                    datos[indice] = resultado['total_envios']
                except ValueError:
                    continue
            
            return jsonify({
                'labels': dias,
                'data': datos
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== RUTAS PARA GESTIÓN DE FRASES =====

@main_bp.route('/frases')
@login_required
def frases():
    """Vista de frases - gestión para administradores, historial para usuarios"""
    # Si es usuario normal, mostrar sus frases recibidas
    if current_user.rol == 'usuario':
        return frases_usuario()
    
    # Si es admin, mostrar gestión completa
    elif current_user.is_admin:
        return frases_admin()
    
    # Si no tiene permisos
    else:
        flash('No tienes permisos para acceder a esta página', 'error')
        return redirect(url_for('main.dashboard'))

def frases_usuario():
    """Vista de frases para usuarios normales - historial de frases recibidas con paginación"""
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 10 registros por página como solicitado
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Consulta base para obtener frases enviadas exitosamente al usuario actual
            query = """
                SELECT f.frase, f.significado, f.ejemplo, 
                       DATE(te.enviado_en) as fecha_envio,
                       te.enviado_en
                FROM trazabilidad_envio te
                JOIN frases_dia f ON te.frase_id = f.id
                WHERE te.usuario_id = %s AND te.resultado = 'exito'
            """
            count_query = """
                SELECT COUNT(*) as total
                FROM trazabilidad_envio te
                JOIN frases_dia f ON te.frase_id = f.id
                WHERE te.usuario_id = %s AND te.resultado = 'exito'
            """
            params = [current_user.id]
            
            # Aplicar filtros de fecha si se proporcionan
            if fecha_desde:
                date_condition = " AND DATE(te.enviado_en) >= %s"
                query += date_condition
                count_query += date_condition
                params.append(fecha_desde)
            
            if fecha_hasta:
                date_condition = " AND DATE(te.enviado_en) <= %s"
                query += date_condition
                count_query += date_condition
                params.append(fecha_hasta)
            
            # Contar total de frases con filtros aplicados
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # Obtener frases paginadas
            offset = (page - 1) * per_page
            query += " ORDER BY te.enviado_en DESC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(query, params)
            mis_frases = cursor.fetchall()
            
            # Calcular paginación
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            return render_template('frases.html', 
                                 mis_frases=mis_frases,
                                 page=page,
                                 total_pages=total_pages,
                                 has_prev=has_prev,
                                 has_next=has_next,
                                 total=total,
                                 fecha_desde=fecha_desde,
                                 fecha_hasta=fecha_hasta)
            
    except Exception as e:
        flash(f'Error al obtener frases: {str(e)}', 'error')
        return render_template('frases.html', mis_frases=[])

def frases_admin():
    """Vista de gestión de frases para administradores"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    dia = request.args.get('dia', '')
    
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Construir la consulta base
            query = 'SELECT id, dia_del_ano, frase, significado, ejemplo, creado_en FROM frases_dia WHERE 1=1'
            count_query = 'SELECT COUNT(*) as total FROM frases_dia WHERE 1=1'
            params = []
            
            # Aplicar filtros
            if search:
                search_condition = ' AND (frase LIKE %s OR significado LIKE %s OR ejemplo LIKE %s)'
                query += search_condition
                count_query += search_condition
                search_param = f'%{search}%'
                params.extend([search_param, search_param, search_param])
            
            if dia:
                dia_condition = ' AND dia_del_ano = %s'
                query += dia_condition
                count_query += dia_condition
                params.append(int(dia))
            
            # Contar total de frases con filtros aplicados
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # Obtener frases paginadas
            offset = (page - 1) * per_page
            query += ' ORDER BY dia_del_ano LIMIT %s OFFSET %s'
            params.extend([per_page, offset])
            
            cursor.execute(query, params)
            frases = cursor.fetchall()
            
            # Calcular paginación
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            return render_template('frases.html', 
                                 frases=frases,
                                 page=page,
                                 total_pages=total_pages,
                                 has_prev=has_prev,
                                 has_next=has_next,
                                 total=total,
                                 search=search,
                                 dia=dia)
    except Exception as e:
        logger.error(f"Error al obtener frases: {e}")
        flash('Error al cargar las frases', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/frases/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_frase(id):
    """Obtiene una frase específica por ID"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM frases_dia WHERE id = %s', (id,))
            frase = cursor.fetchone()
            
            if frase:
                return jsonify(frase)
            else:
                return jsonify({'error': 'Frase no encontrada'}), 404
    except Exception as e:
        logger.error(f"Error al obtener frase {id}: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/frases/guardar', methods=['POST'])
@login_required
@admin_required
def guardar_frase():
    """Guarda o actualiza una frase"""
    try:
        data = request.get_json()
        frase_id = data.get('id')
        dia_del_ano = data.get('dia_del_ano')
        frase = data.get('frase')
        significado = data.get('significado')
        ejemplo = data.get('ejemplo')
        
        # Normalizar frase_id - convertir cadena vacía a None
        if frase_id == '' or frase_id == 'None':
            frase_id = None
        
        # Validaciones
        if not dia_del_ano or not frase:
            return jsonify({'error': 'Día del año y frase son requeridos'}), 400
            
        try:
            dia_del_ano = int(dia_del_ano)
        except (ValueError, TypeError):
            return jsonify({'error': 'El día del año debe ser un número válido'}), 400
            
        if not (1 <= dia_del_ano <= 365):
            return jsonify({'error': 'El día del año debe estar entre 1 y 365'}), 400
        
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            
            if frase_id:  # Actualizar
                # Verificar que no exista otro registro con el mismo día del año
                cursor.execute('SELECT id FROM frases_dia WHERE dia_del_ano = %s AND id != %s', 
                             (dia_del_ano, frase_id))
                if cursor.fetchone():
                    return jsonify({'error': f'Ya existe una frase para el día {dia_del_ano}'}), 400
                
                cursor.execute("""
                    UPDATE frases_dia 
                    SET dia_del_ano = %s, frase = %s, significado = %s, ejemplo = %s
                    WHERE id = %s
                """, (dia_del_ano, frase, significado, ejemplo, frase_id))
                mensaje = 'Frase actualizada exitosamente'
            else:  # Crear
                # Verificar que no exista una frase para ese día
                cursor.execute('SELECT id FROM frases_dia WHERE dia_del_ano = %s', (dia_del_ano,))
                if cursor.fetchone():
                    return jsonify({'error': f'Ya existe una frase para el día {dia_del_ano}'}), 400
                
                cursor.execute("""
                    INSERT INTO frases_dia (dia_del_ano, frase, significado, ejemplo)
                    VALUES (%s, %s, %s, %s)
                """, (dia_del_ano, frase, significado, ejemplo))
                mensaje = 'Frase creada exitosamente'
            
            conn.commit()
            return jsonify({'success': True, 'message': mensaje})
            
    except Exception as e:
        logger.error(f"Error al guardar frase: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/frases/<int:id>/eliminar', methods=['DELETE'])
@login_required
@admin_required
def eliminar_frase(id):
    """Elimina una frase"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar que la frase existe
            cursor.execute('SELECT id FROM frases_dia WHERE id = %s', (id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Frase no encontrada'}), 404
            
            # Eliminar la frase
            cursor.execute('DELETE FROM frases_dia WHERE id = %s', (id,))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Frase eliminada exitosamente'})
            
    except Exception as e:
        logger.error(f"Error al eliminar frase {id}: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/stats/estado-envios')
@login_required
@admin_required
def get_estado_envios():
    """Endpoint para obtener estadísticas del estado de envíos (solo admin)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT 
                    resultado,
                    COUNT(*) as total
                FROM trazabilidad_envio
                WHERE enviado_en >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY resultado
            """
            cursor.execute(query)
            resultados = cursor.fetchall()
            
            # Formatear datos para la gráfica
            estados = {'exito': 0, 'error': 0}
            for resultado in resultados:
                if resultado['resultado'] in estados:
                    estados[resultado['resultado']] = resultado['total']
            
            return jsonify({
                'labels': ['Exitosos', 'Fallidos'],
                'data': [estados['exito'], estados['error']]
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/stats/errores-detallados')
@login_required
@admin_required
def get_errores_detallados():
    """Endpoint para obtener análisis detallado de errores (solo admin)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Clasificar errores por tipo
            query = """
                SELECT 
                    descripcion_error,
                    COUNT(*) as total
                FROM trazabilidad_envio
                WHERE resultado = 'error' 
                AND descripcion_error IS NOT NULL
                AND enviado_en >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY descripcion_error
                ORDER BY total DESC
                LIMIT 10
            """
            cursor.execute(query)
            errores = cursor.fetchall()
            
            # Clasificar errores de red vs otros
            errores_red = 0
            otros_errores = 0
            errores_detalle = []
            
            network_keywords = ['network', 'unreachable', 'connection', 'timeout', 'refused', 'reset']
            
            for error in errores:
                descripcion = error['descripcion_error'].lower()
                es_error_red = any(keyword in descripcion for keyword in network_keywords)
                
                if es_error_red:
                    errores_red += error['total']
                else:
                    otros_errores += error['total']
                
                errores_detalle.append({
                    'descripcion': error['descripcion_error'][:50] + '...' if len(error['descripcion_error']) > 50 else error['descripcion_error'],
                    'total': error['total'],
                    'tipo': 'Red' if es_error_red else 'Otro'
                })
            
            return jsonify({
                'resumen': {
                    'labels': ['Errores de Red', 'Otros Errores'],
                    'data': [errores_red, otros_errores]
                },
                'detalle': errores_detalle
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/stats/usuarios-por-tipo')
@login_required
@admin_required
def get_usuarios_por_tipo():
    """Endpoint para obtener estadísticas de usuarios por tipo de suscripción (solo admin)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Usuarios por tipo
            query = """
                SELECT 
                    tipo_suscripcion,
                    COUNT(*) as total_usuarios,
                    SUM(CASE WHEN activo = TRUE THEN 1 ELSE 0 END) as usuarios_activos
                FROM usuarios
                GROUP BY tipo_suscripcion
            """
            cursor.execute(query)
            usuarios_tipo = cursor.fetchall()
            
            # Envíos exitosos por tipo en los últimos 30 días
            query_envios = """
                SELECT 
                    u.tipo_suscripcion,
                    COUNT(te.id) as envios_exitosos
                FROM usuarios u
                LEFT JOIN trazabilidad_envio te ON u.id = te.usuario_id 
                    AND te.resultado = 'exito'
                    AND te.enviado_en >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY u.tipo_suscripcion
            """
            cursor.execute(query_envios)
            envios_tipo = cursor.fetchall()
            
            # Combinar datos
            resultado = {}
            for usuario in usuarios_tipo:
                tipo = usuario['tipo_suscripcion']
                resultado[tipo] = {
                    'total_usuarios': usuario['total_usuarios'],
                    'usuarios_activos': usuario['usuarios_activos'],
                    'envios_exitosos': 0
                }
            
            for envio in envios_tipo:
                tipo = envio['tipo_suscripcion']
                if tipo in resultado:
                    resultado[tipo]['envios_exitosos'] = envio['envios_exitosos']
            
            return jsonify({
                'labels': list(resultado.keys()),
                'datasets': [
                    {
                        'label': 'Total Usuarios',
                        'data': [resultado[tipo]['total_usuarios'] for tipo in resultado.keys()],
                        'backgroundColor': 'rgba(54, 162, 235, 0.8)'
                    },
                    {
                        'label': 'Usuarios Activos',
                        'data': [resultado[tipo]['usuarios_activos'] for tipo in resultado.keys()],
                        'backgroundColor': 'rgba(75, 192, 192, 0.8)'
                    },
                    {
                        'label': 'Envíos Exitosos (30d)',
                        'data': [resultado[tipo]['envios_exitosos'] for tipo in resultado.keys()],
                        'backgroundColor': 'rgba(153, 102, 255, 0.8)'
                    }
                ]
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/stats/rendimiento-envios')
@login_required
@admin_required
def get_rendimiento_envios():
    """Endpoint para obtener métricas de rendimiento de envíos (solo admin)"""
    try:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Envíos por hora del día (últimos 7 días)
            query = """
                SELECT 
                    HOUR(enviado_en) as hora,
                    COUNT(*) as total_envios,
                    SUM(CASE WHEN resultado = 'exito' THEN 1 ELSE 0 END) as envios_exitosos
                FROM trazabilidad_envio
                WHERE enviado_en >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY HOUR(enviado_en)
                ORDER BY hora
            """
            cursor.execute(query)
            envios_hora = cursor.fetchall()
            
            # Preparar datos para gráfico de 24 horas
            horas = list(range(24))
            datos_total = [0] * 24
            datos_exitosos = [0] * 24
            
            for envio in envios_hora:
                hora = envio['hora']
                datos_total[hora] = envio['total_envios']
                datos_exitosos[hora] = envio['envios_exitosos']
            
            # Calcular tasa de éxito por hora
            tasa_exito = []
            for i in range(24):
                if datos_total[i] > 0:
                    tasa_exito.append(round((datos_exitosos[i] / datos_total[i]) * 100, 1))
                else:
                    tasa_exito.append(0)
            
            return jsonify({
                'labels': [f'{h:02d}:00' for h in horas],
                'datasets': [
                    {
                        'label': 'Total Envíos',
                        'data': datos_total,
                        'borderColor': 'rgb(75, 192, 192)',
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                        'yAxisID': 'y'
                    },
                    {
                        'label': 'Tasa de Éxito (%)',
                        'data': tasa_exito,
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'yAxisID': 'y1'
                    }
                ]
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500