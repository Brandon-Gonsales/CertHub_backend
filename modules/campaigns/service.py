import uuid
import string
import random
import pandas as pd
import os
from fastapi import UploadFile, HTTPException, status
from typing import Dict, List
from .schemas import Campaign, TemplateDetails, Student

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
        if 'nombre' not in df.columns or 'nombres' not in df.columns or 'correo' not in df.columns or 'correos' not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo Excel debe contener las columnas 'nombre' y 'correo' ó 'nombres' y 'correos'."
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
        correo = row['correo']
        
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