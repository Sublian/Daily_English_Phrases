from werkzeug.security import generate_password_hash
import mysql.connector
from config import Config

def set_admin_password(password):
    try:
        conn = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = conn.cursor()
        
        password_hash = generate_password_hash(password)
        cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = 1', (password_hash,))
        conn.commit()
        
        print('Contraseña de admin actualizada exitosamente')
    except Exception as e:
        print(f'Error al actualizar la contraseña: {e}')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    set_admin_password('devadmin')