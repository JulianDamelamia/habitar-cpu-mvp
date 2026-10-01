
from app.models.user import User


def enviar_mail_verificacion(contenido:list[dict]) -> None:

    for usuario in contenido:
        print(f'Hola {usuario['nombre']} {usuario['apellido']},\ningresá a habitardigital.com con tu dirección de correo {usuario['email']} y contraseña {usuario['password_temporal']}')