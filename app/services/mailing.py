
from app.models.user import User


def enviar_mail_verificacion(datos_mails:list[dict]) -> None:

    for usuario in datos_mails:
        print(f'Mail de mentira enviado a {usuario['nombre']} {usuario['apellido']} al correo {usuario['email']}')