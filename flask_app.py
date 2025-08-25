import logging
from flask import Flask
from config import Config
from routes import main_bp
from auth import auth_bp, login_manager
from database import DatabaseManager

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Factory function para crear la aplicación Flask"""
    app = Flask(__name__, template_folder='templates')

    # Configurar la aplicación
    app.config.from_object(Config)

    # Inicializar el login manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'

    # Inicializar la base de datos
    DatabaseManager.initialize_pool()

    # Registrar blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    @app.template_filter('title')
    def title_filter(s):
        return s.title() if s else s

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=Config.DEBUG)