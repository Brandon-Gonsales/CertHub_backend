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

import io
import os
from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _find_student_and_campaign_by_code(code: str):
    """
    Busca en toda la 'base de datos' un estudiante por su código único.
    Devuelve el estudiante y la campaña a la que pertenece.
    """
    for campaign in db.values():
        for student in campaign.students:
            if student.codigo == code:
                return student, campaign
    return None, None


def _generate_certificate(student_name: str, template: TemplateDetails):
    """
    Genera el certificado en PDF escribiendo el nombre del estudiante
    sobre la plantilla base (imagen o PDF).
    """
    base_path = template.certificate_path
    
    # -------------------------------------------------------------------
    # ESTA ES LA PARTE NUEVA QUE ARREGLA EL PROBLEMA
    # -------------------------------------------------------------------
    
    # Esto es lo que envía tu frontend (ej: "001")
    font_identifier = template.font_family 
    font_path = None
    
    # Paso A: Leemos todos los archivos que hay en la carpeta "fonts"
    try:
        # ¡IMPORTANTE! Si tu carpeta se llama "fuentes", cambia "fonts" a "fuentes" aquí abajo.
        available_fonts = os.listdir("fonts") 
        
        # Paso B: Buscamos un archivo que contenga el identificador
        for filename in available_fonts:
            # Esta línea comprueba si "001" está dentro del nombre "font_001.ttf"
            if font_identifier in filename:
                # ¡Lo encontramos! Guardamos la ruta completa
                font_path = os.path.join("fonts", filename) # De nuevo, cambia "fonts" si es necesario
                break 
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="La carpeta 'fonts' no se encuentra en el servidor.")

    # Paso C: Si no encontramos ninguna fuente, devolvemos un error claro
    if not font_path:
        raise HTTPException(status_code=500, detail=f"La fuente con el identificador '{font_identifier}' no se encuentra en el servidor.")
    
    # -------------------------------------------------------------------
    # EL RESTO DEL CÓDIGO AHORA USA LA RUTA CORRECTA QUE ENCONTRAMOS
    # -------------------------------------------------------------------

    buffer = io.BytesIO()
    
    if base_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        with Image.open(base_path) as img:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(font_path, template.font_size)
            draw.text((template.x, template.y), student_name, font=font, fill="black")
            img.convert('RGB').save(buffer, format='PDF')

    elif base_path.lower().endswith('.pdf'):
        existing_pdf = PdfReader(open(base_path, "rb"))
        page = existing_pdf.pages[0]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))

        font_name = os.path.splitext(os.path.basename(font_path))[0]
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        c.setFont(font_name, template.font_size)
        
        y_coordinate = page_height - template.y - template.font_size
        c.drawString(template.x, y_coordinate, student_name)
        c.save()

        packet.seek(0)
        new_pdf = PdfReader(packet)
        page.merge_page(new_pdf.pages[0])

        writer = PdfWriter()
        writer.add_page(page)
        writer.write(buffer)
    else:
        raise HTTPException(status_code=400, detail="El formato del certificado no es compatible.")

    buffer.seek(0)
    return buffer


def get_certificate_by_code(code: str):
    """
    Función principal del servicio para obtener un certificado.
    """
    student, campaign = _find_student_and_campaign_by_code(code)

    if not student or not campaign:
        raise HTTPException(status_code=404, detail="Código de certificado no válido o no encontrado.")
    
    if not campaign.template_details:
        raise HTTPException(status_code=400, detail="La campaña de este certificado no tiene una plantilla configurada.")

    # Generamos el PDF dinámicamente
    pdf_buffer = _generate_certificate(student.nombre, campaign.template_details)
    
    return pdf_buffer

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