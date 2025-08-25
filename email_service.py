import smtplib
import logging
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
from config import Config

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de correos electrónicos"""

    def __init__(self, email_config: Dict[str, Any]):
        self.config = email_config
        self._validar_configuracion()

    def _validar_configuracion(self):
        """Valida que la configuración de email esté completa"""
        required_keys = ['user', 'password', 'smtp_server', 'smtp_port']
        for key in required_keys:
            if not self.config.get(key):
                raise ValueError(f"Configuración de email incompleta: falta {key}")

    def crear_mensaje(self, frase_data: Dict[str, Any], usuario: Dict[str, Any]) -> MIMEMultipart:
        """Crea el mensaje de correo personalizado para cada usuario"""
        msg = MIMEMultipart('alternative')

        # Personalizar saludo según tipo de suscripción
        if usuario.get('tipo_suscripcion', '').lower() == 'premium':
            subject = "✨💎 Frase Diaria Premium - Inspiración Exclusiva 💎✨"
            saludo_tipo = "🌟 **PREMIUM** 🌟"
            nombre_usuario = usuario.get('nombre') or "Suscriptor Premium"
        else:
            subject = "📩 Frase del Día - Inspiración Diaria"
            saludo_tipo = ""
            nombre_usuario = usuario.get('nombre') or "Amigo"

        # Headers del mensaje
        msg['Subject'] = subject
        msg['From'] = self.config['user']
        msg['To'] = usuario['email']
        msg['X-Priority'] = '3'

        # Contenido en texto plano
        texto_plano = self._crear_contenido_texto(frase_data, nombre_usuario, saludo_tipo, usuario)

        # Contenido en HTML
        html = self._crear_contenido_html(frase_data, nombre_usuario, saludo_tipo, usuario)

        # Adjuntar ambas versiones
        msg.attach(MIMEText(texto_plano, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        return msg

    def _crear_contenido_texto(self, frase_data: Dict[str, Any], nombre_usuario: str,
                              saludo_tipo: str, usuario: Dict[str, Any]) -> str:
        """Crea el contenido en texto plano del email"""
        es_premium = usuario.get('tipo_suscripcion', '').lower() == 'premium'

        contenido = f"""
Hola {nombre_usuario},

{saludo_tipo}
{'🎯 Tu inspiración premium del día está aquí:' if es_premium else 'Aquí tienes tu frase inspiradora del día:'}

📌 FRASE: {frase_data.get('frase', 'N/A')}

🧠 SIGNIFICADO: {frase_data.get('significado', 'N/A')}

🗣️ EJEMPLO DE USO: {frase_data.get('ejemplo', 'N/A')}

{'💎 Gracias por ser parte de nuestra comunidad Premium!' if es_premium else '¡Que tengas un día lleno de aprendizaje y crecimiento!'}

────────────────────────────────
📅 Enviado el: {datetime.now(Config.LOCAL_TZ).strftime('%d/%m/%Y a las %H:%M')}
🤖 Sistema automático de frases diarias
{'✨ Versión Premium' if es_premium else ''}
        """.strip()

        return contenido

    def _crear_contenido_html(self, frase_data: Dict[str, Any], nombre_usuario: str,
                             saludo_tipo: str, usuario: Dict[str, Any]) -> str:
        """Crea el contenido HTML del email"""
        es_premium = usuario.get('tipo_suscripcion', '').lower() == 'premium'

        # Colores y estilos según tipo de suscripción
        if es_premium:
            color_principal = "#d4af37"  # Dorado
            color_secundario = "#f8f9fa"
            color_acento = "#6f42c1"
            banner_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"
            titulo_extra = "✨💎 PREMIUM 💎✨"
        else:
            color_principal = "#2c5aa0"
            color_secundario = "#f8f9fa"
            color_acento = "#495057"
            banner_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"
            titulo_extra = ""

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; box-shadow: 0 0 20px rgba(0,0,0,0.1);">

              <!-- Header Premium/Normal -->
              <div style="{banner_style} color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">
                  📩 Frase del Día {titulo_extra}
                </h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Inspiración diaria para tu crecimiento</p>
              </div>

              <!-- Contenido principal -->
              <div style="padding: 30px 20px;">
                <h2 style="color: {color_principal}; margin-top: 0; font-size: 20px;">
                  Hola {nombre_usuario} {'🌟' if es_premium else '😊'},
                </h2>

                <p style="color: #666; font-size: 16px;">
                  {'🎯 Tu inspiración premium del día está aquí:' if es_premium else 'Aquí tienes tu frase inspiradora del día:'}
                </p>

                <!-- Tarjeta de la frase -->
                <div style="background: linear-gradient(135deg, {color_secundario} 0%, #ffffff 100%);
                           padding: 25px; border-radius: 12px; margin: 25px 0;
                           border-left: 5px solid {color_principal}; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

                  <div style="margin-bottom: 20px;">
                    <h3 style="color: {color_acento}; margin: 0 0 10px 0; font-size: 16px;">
                      📌 Frase del día:
                    </h3>
                    <p style="font-size: 20px; font-style: italic; color: #212529;
                              font-weight: 500; margin: 0; line-height: 1.4;">
                      "{frase_data.get('frase', 'N/A')}"
                    </p>
                  </div>

                  <div style="margin-bottom: 20px;">
                    <h3 style="color: {color_acento}; margin: 0 0 10px 0; font-size: 16px;">
                      🧠 Significado:
                    </h3>
                    <p style="margin: 0; color: #495057; line-height: 1.5;">
                      {frase_data.get('significado', 'N/A')}
                    </p>
                  </div>

                  <div>
                    <h3 style="color: {color_acento}; margin: 0 0 10px 0; font-size: 16px;">
                      🗣️ Ejemplo de uso:
                    </h3>
                    <p style="margin: 0; color: #6c757d; font-style: italic; line-height: 1.5;">
                      {frase_data.get('ejemplo', 'N/A')}
                    </p>
                  </div>
                </div>

                <!-- Mensaje de agradecimiento -->
                <div style="text-align: center; padding: 20px; background-color: {color_secundario};
                           border-radius: 8px; margin: 20px 0;">
                  <p style="color: {color_principal}; font-weight: 500; margin: 0; font-size: 16px;">
                    {'💎 ¡Gracias por ser parte de nuestra comunidad Premium!' if es_premium else '¡Que tengas un día lleno de aprendizaje y crecimiento!'}
                  </p>
                </div>

              </div>

              <!-- Footer -->
              <div style="background-color: #f8f9fa; padding: 20px; text-align: center;
                         border-top: 1px solid #dee2e6; color: #6c757d; font-size: 14px;">
                <p style="margin: 0 0 10px 0;">
                  📅 Enviado el: {datetime.now(Config.LOCAL_TZ).strftime('%d/%m/%Y a las %H:%M')}
                </p>
                <p style="margin: 0;">
                  🤖 Sistema automático de frases diarias {'✨ Versión Premium' if es_premium else ''}
                </p>
              </div>

            </div>
          </body>
        </html>
        """

        return html

    def enviar_correo(self, frase_data: Dict[str, Any], usuario: Dict[str, Any]) -> bool:
        """Envía el correo electrónico a un usuario específico con reintentos"""
        max_intentos = 3

        for intento in range(1, max_intentos + 1):
            try:
                logger.info(f"Enviando a {usuario['email']} - Intento {intento}")

                msg = self.crear_mensaje(frase_data, usuario)

                with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                    server.starttls()
                    server.login(self.config['user'], self.config['password'])
                    server.send_message(msg)

                logger.info(f"✅ Correo enviado exitosamente a {usuario['email']}")
                return True

            except smtplib.SMTPException as e:
                logger.error(f"❌ Error SMTP enviando a {usuario['email']} - Intento {intento}: {e}")
                if intento < max_intentos:
                    tiempo_espera = intento * 2
                    logger.info(f"Reintentando en {tiempo_espera} segundos...")
                    time.sleep(tiempo_espera)
            except Exception as e:
                logger.error(f"❌ Error inesperado enviando a {usuario['email']} - Intento {intento}: {e}")
                if intento < max_intentos:
                    time.sleep(intento * 2)

        logger.error(f"💥 Falló el envío a {usuario['email']} después de todos los intentos")
        return False

    def enviar_masivo(self, frase_data: Dict[str, Any], usuarios: List[Dict[str, Any]]) -> Dict[str, int]:
        """Envía emails a múltiples usuarios y retorna estadísticas"""
        resultados = {'exitosos': 0, 'fallidos': 0, 'total': len(usuarios)}

        logger.info(f"📧 Iniciando envío masivo a {resultados['total']} usuarios")

        for i, usuario in enumerate(usuarios, 1):
            logger.info(f"📤 Procesando usuario {i}/{resultados['total']}: {usuario['email']}")

            if self.enviar_correo(frase_data, usuario):
                resultados['exitosos'] += 1
            else:
                resultados['fallidos'] += 1

            # Pausa pequeña entre envíos para evitar ser marcado como spam
            if i < len(usuarios):
                time.sleep(1)

        logger.info(f"📊 Envío masivo completado - Exitosos: {resultados['exitosos']}, Fallidos: {resultados['fallidos']}")
        return resultados