# Trae Correo - Sistema de Envío de Frases Diarias

Un sistema web completo para el envío automatizado de frases diarias por correo electrónico, con gestión de usuarios y panel de administración.

## Características Principales

- 📧 **Envío automatizado** de frases diarias por correo electrónico
- 👥 **Gestión de usuarios** con diferentes tipos de suscripción (gratuito, premium)
- 🔐 **Sistema de autenticación** completo con roles (usuario, admin, pendiente)
- ✉️ **Confirmación por email** para nuevos usuarios con tokens seguros
- 📊 **Dashboard personalizado** con estadísticas específicas por usuario
- 🎯 **Gestión de frases** con categorías y personalización
- 📈 **Trazabilidad completa** de envíos y errores
- 🔄 **Sistema de reintentos** para envíos fallidos
- 📱 **Interfaz responsive** con Bootstrap y estilos mejorados
- 🔒 **Perfiles de usuario** con campos bloqueados y actualización automática
- 📄 **Paginación** en listados de frases para mejor rendimiento
- 📊 **Métricas avanzadas** y reportes de rendimiento

## Requisitos

- Python 3.8+
- MySQL 8.0+
- Cuenta de Gmail con contraseña de aplicación
- Variables de entorno configuradas

## Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd <nombre-del-directorio>
```

2. Crear y activar entorno virtual:
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno en el archivo `.env`:
```env
# Configuración de Email (Gmail)
EMAIL_USER=your_gmail@gmail.com
EMAIL_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Configuración de la Base de Datos
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_NAME=frases_db

# Configuración de la Aplicación
FLASK_SECRET_KEY=generate_a_secure_random_key_here
FLASK_DEBUG=True
LOG_LEVEL=INFO
MAX_RETRY_ATTEMPTS=3
```

5. Crear la base de datos:
```bash
# Ejecutar el script SQL de la estructura inicial
mysql -u your_db_user -p your_db_name < database_template.txt

# Ejecutar las migraciones
mysql -u your_db_user -p your_db_name < stable/migrations/001_add_auth_fields.sql
mysql -u your_db_user -p your_db_name < stable/migrations/002_set_admin_user.sql
mysql -u your_db_user -p your_db_name < stable/migrations/003_add_pendiente_role.sql
```

## Estructura del Proyecto

```
stable/
├── auth.py              # Autenticación y autorización con Flask-Login
├── config.py            # Configuración de la aplicación
├── database.py          # Conexión a base de datos con pool de conexiones
├── email_service.py     # Servicio de envío de correos
├── flask_app.py         # Aplicación principal Flask
├── frase_service.py     # Servicio de gestión de frases
├── models.py            # Modelos y servicios (UserService, StatsService)
├── routes.py            # Rutas de la aplicación (830 líneas)
├── user_service.py      # Servicio especializado de usuarios
├── token_service.py     # Servicio de tokens para confirmación
├── migrations/          # Scripts de migración de base de datos
│   ├── 001_add_auth_fields.sql
│   ├── 002_set_admin_user.sql
│   └── 003_add_pendiente_role.sql
├── scripts/             # Scripts de utilidad y mantenimiento
│   ├── run_migrations.py      # Ejecutor automático de migraciones
│   ├── set_admin_password.py  # Configuración de contraseña admin
│   ├── set_default_passwords.py # Configuración de contraseñas por defecto
│   └── test/                   # Scripts de testing
│       ├── test_confirmation_flow.py  # Test del flujo de confirmación
│       ├── test_email_functionality.py # Test de funcionalidad de email
│       └── test_envio_mejorado.py     # Test de envío mejorado
└── templates/           # Plantillas HTML con Bootstrap
    ├── base.html
    ├── dashboard.html
    ├── profile.html
    ├── frases.html
    ├── usuarios.html
    ├── login.html
    └── establecer_password.html
```

## Consideraciones de Seguridad

1. **Autenticación:**
   - Hashing seguro de contraseñas con Werkzeug
   - Tokens JWT para confirmación de email
   - Sistema de roles y permisos granular

2. **Configuración:**
   - Variables de entorno para datos sensibles
   - Contraseñas de aplicación específicas para Gmail
   - Validación de entrada en todos los formularios

3. **Base de datos:**
   - Consultas preparadas para prevenir SQL injection
   - Índices optimizados para búsquedas seguras
   - Backups regulares automatizados

4. **Aplicación:**
   - Rate limiting implementado
   - Logging de seguridad detallado
   - Manejo seguro de sesiones con Flask-Login

## Estado Actual de Desarrollo

✅ **Completado:**
- Sistema de autenticación completo con roles
- Confirmación de email con tokens seguros
- Dashboard personalizado para usuarios
- Gestión avanzada de usuarios y frases
- Paginación en listados
- Perfiles con campos bloqueados y estilos mejorados
- Métricas y estadísticas detalladas
- Sistema de envío de correos robusto

## Próximos Pasos

🎯 **Mejoras Planificadas:**

1. **Inmediato (En Progreso):**
   - ✅ Reorganización de scripts en carpetas dedicadas
   - 🔄 Implementar tests automatizados (unitarios e integración)
     - Tests para servicios principales (UserService, EmailService, TokenService)
     - Tests de integración para flujos completos
     - Cobertura de código con pytest-cov
   - 📝 Mejorar documentación de API con ejemplos prácticos
   - ⚡ Optimizar consultas de base de datos con análisis de rendimiento

2. **Corto plazo (Próximas 2-4 semanas):**
   - 🔌 API REST completa para gestión de frases
     - Endpoints CRUD para frases con autenticación
     - Documentación OpenAPI/Swagger
     - Rate limiting y validación de entrada
   - 📧 Sistema de plantillas de email personalizables
     - Editor visual de plantillas
     - Variables dinámicas y personalización
     - Preview de emails antes del envío
   - 📊 Integración con sistemas de monitoreo
     - Métricas de rendimiento en tiempo real
     - Alertas automáticas por errores
     - Dashboard de salud del sistema

3. **Mediano plazo (1-3 meses):**
   - 🔔 Sistema de notificaciones push
   - 📈 Análisis de engagement de usuarios
   - ⚡ Implementar caché para mejor rendimiento
   - 🔐 Autenticación OAuth2 y SSO

4. **Largo plazo (3+ meses):**
   - 🔗 Integración con servicios de terceros
   - 🤖 Sistema de recomendaciones de frases con IA
   - 📱 Aplicación móvil complementaria
   - 🌐 Soporte multi-idioma

## Monitoreo y Mantenimiento

- Usar servicios como UptimeRobot para monitoreo
- Implementar logging comprehensivo
- Realizar backups automáticos
- Mantener dependencias actualizadas
- Monitoreo de métricas de rendimiento

## Contribuir

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/NuevaFuncionalidad`)
3. Commit tus cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/NuevaFuncionalidad`)
5. Abrir un Pull Request

## Licencia

Distribuido bajo la Licencia MIT. Ver `LICENSE` para más información.

