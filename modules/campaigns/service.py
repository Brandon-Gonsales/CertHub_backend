import uuid
import string
import random
import pandas as pd
import os
from fastapi import UploadFile, HTTPException, status
from typing import Dict, List
from .schemas import Campaign, TemplateDetails, Student
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from core.config import settings
import asyncio 

# Creamos un directorio para guardar los archivos subidos
UPLOAD_DIRECTORY = "./uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# Usaremos un diccionario en memoria para simular una base de datos.
# La clave será el campaign_id y el valor será el objeto Campaign.
db: Dict[str, Campaign] = {}

def create_new_campaign() -> str:
    """Crea una nueva campaña y la guarda en la 'base de datos'."""
    campaign_id = str(uuid.uuid4())
    db[campaign_id] = Campaign(id=campaign_id)
    return campaign_id

def _get_campaign_or_404(campaign_id: str) -> Campaign:
    """Función auxiliar para obtener una campaña o lanzar un error 404."""
    campaign = db.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    return campaign

def update_campaign_template(
    campaign_id: str,
    x: int,
    y: int,
    font_size: int,
    font_family: str,
    certificate: UploadFile
) -> Campaign:
    """Actualiza los detalles de la plantilla de una campaña."""
    campaign = _get_campaign_or_404(campaign_id)

    # Guarda el archivo en el servidor
    file_path = os.path.join(UPLOAD_DIRECTORY, f"{campaign_id}_{certificate.filename}")
    with open(file_path, "wb") as buffer:
        buffer.write(certificate.file.read())

    # Crea el objeto con los detalles de la plantilla
    template_data = TemplateDetails(
        x=x,
        y=y,
        font_size=font_size,
        font_family=font_family,
        certificate_path=file_path
    )
    
    campaign.template_details = template_data
    return campaign

def _generate_unique_code(length: int = 8) -> str:
    """Genera un código alfanumérico único (Mayúsculas y dígitos)."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

def update_campaign_students(campaign_id: str, students_file: UploadFile) -> int:
    """Procesa un archivo Excel y añade los estudiantes a una campaña."""
    campaign = _get_campaign_or_404(campaign_id)
    
    try:
        # Leemos el archivo excel usando pandas
        df = pd.read_excel(students_file.file)
        
        # Normalizamos los nombres de las columnas (a minúsculas y sin espacios)
        df.columns = [col.strip().lower() for col in df.columns]

        # Verificamos que las columnas 'nombres' y 'correo' existan
        if 'nombres' not in df.columns or 'correos' not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo Excel debe contener las columnas 'nombres' y 'correo'."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar el archivo Excel: {e}"
        )

    new_students: List[Student] = []
    # Generamos un conjunto de códigos ya existentes para evitar duplicados en esta carga
    existing_codes = {student.codigo for student in campaign.students}

    for index, row in df.iterrows():
        nombre = row['nombres']
        correo = row['correos']
        
        # Generamos un código único que no exista ya en la campaña
        while True:
            code = _generate_unique_code()
            if code not in existing_codes:
                existing_codes.add(code)
                break
        
        new_students.append(Student(nombre=str(nombre), correo=str(correo), codigo=code))
    
    campaign.students.extend(new_students)
    return len(new_students)


def update_campaign_message(campaign_id: str, message: str) -> Campaign:
    """Actualiza el mensaje del email para una campaña."""
    campaign = _get_campaign_or_404(campaign_id)
    campaign.email_message = message
    return campaign

async def _send_emails_in_background(campaign: Campaign, fixed_url: str):
    """
    Esta función se ejecuta en segundo plano para enviar los correos.
    """
    # Configuración de conexión usando las variables de entorno
    conf = ConnectionConfig(
        MAIL_USERNAME = settings.MAIL_USERNAME,
        MAIL_PASSWORD = settings.MAIL_PASSWORD,
        MAIL_FROM = settings.MAIL_FROM,
        MAIL_PORT = settings.MAIL_PORT,
        MAIL_SERVER = settings.MAIL_SERVER,
        MAIL_STARTTLS = settings.MAIL_STARTTLS,
        MAIL_SSL_TLS = settings.MAIL_SSL_TLS,
        USE_CREDENTIALS = True,
        VALIDATE_CERTS = True
    )

    print(f"Iniciando envío de correos para la campaña: {campaign.id}")

    # Iteramos sobre cada estudiante en la campaña
    for student in campaign.students:
        # Personalizamos el mensaje reemplazando los placeholders
        # ¡IMPORTANTE! El mensaje debe contener {codigo} y {url}
        personalized_body = campaign.email_message.format(
            nombre=student.nombre,
            codigo=student.codigo,
            url=fixed_url
        )
        
        message = MessageSchema(
            subject=f"Tu código único para la campaña", # Asunto del correo
            recipients=[student.correo],
            body=personalized_body,
            subtype="html" # Puedes usar "plain" o "html"
        )

        fm = FastMail(conf)
        try:
            await fm.send_message(message)
            print(f"Correo enviado exitosamente a {student.correo}")
        except Exception as e:
            print(f"Error al enviar correo a {student.correo}: {e}")

        await asyncio.sleep(1) # Pequeña pausa para no saturar el servidor SMTP


def activate_campaign_and_send_emails(
    campaign_id: str, 
    fixed_url: str,
    background_tasks: BackgroundTasks
):
    """
    Valida la campaña y añade la tarea de envío de correos al segundo plano.
    """
    campaign = _get_campaign_or_404(campaign_id)

    # Validaciones previas
    if not campaign.students:
        raise HTTPException(status_code=400, detail="La campaña no tiene estudiantes. Sube el archivo Excel primero.")
    if not campaign.email_message:
        raise HTTPException(status_code=400, detail="La campaña no tiene un mensaje de correo configurado.")

    # Añadimos la función de envío a las tareas en segundo plano
    # La aplicación responderá inmediatamente al usuario mientras esto se ejecuta por detrás.
    background_tasks.add_task(_send_emails_in_background, campaign, fixed_url)
    
    return {"message": "La campaña ha sido activada. El envío de correos ha comenzado en segundo plano."}