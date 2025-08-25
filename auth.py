from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import DatabaseManager
from functools import wraps

auth_bp = Blueprint('auth', __name__)
login_manager = LoginManager()

class User(UserMixin):
    def __init__(self, id, email, nombre, tipo_suscripcion, rol='usuario'):
        self.id = id
        self.email = email
        self.nombre = nombre
        self.tipo_suscripcion = tipo_suscripcion
        self.rol = rol
        self.is_admin = rol == 'admin'

    @staticmethod
    def get(user_id):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM usuarios WHERE id = %s', (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    nombre=user_data['nombre'],
                    tipo_suscripcion=user_data['tipo_suscripcion'],
                    rol=user_data.get('rol', 'usuario')
                )
        return None

    @staticmethod
    def set_admin_password(password):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            password_hash = generate_password_hash(password)
            cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = 1', (password_hash,))
            conn.commit()
            return True

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM usuarios WHERE email = %s', (email,))
            user_data = cursor.fetchone()
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(
                    id=user_data['id'],
                    email=user_data['email'],
                    nombre=user_data['nombre'],
                    tipo_suscripcion=user_data['tipo_suscripcion'],
                    rol=user_data.get('rol', 'usuario')
                )
                login_user(user)
                flash('Inicio de sesión exitoso!', 'success')
                return redirect(url_for('main.dashboard'))
            
        flash('Email o contraseña incorrectos', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión exitosamente', 'success')
    return redirect(url_for('main.dashboard'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Actualizar nombre
            if nombre:
                cursor.execute('UPDATE usuarios SET nombre = %s WHERE id = %s',
                              (nombre, current_user.id))
                flash('Nombre actualizado exitosamente', 'success')
            
            # Actualizar contraseña
            if current_password and new_password:
                cursor.execute('SELECT password_hash FROM usuarios WHERE id = %s',
                              (current_user.id,))
                user_data = cursor.fetchone()
                
                if user_data and check_password_hash(user_data['password_hash'], current_password):
                    new_password_hash = generate_password_hash(new_password)
                    cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = %s',
                                  (new_password_hash, current_user.id))
                    flash('Contraseña actualizada exitosamente', 'success')
                else:
                    flash('La contraseña actual es incorrecta', 'error')
            
            conn.commit()
    
    return render_template('profile.html')