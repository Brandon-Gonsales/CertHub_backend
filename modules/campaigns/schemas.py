from pydantic import BaseModel, Field
from typing import List, Optional

# Esquema para representar a un estudiante individual
class Student(BaseModel):
    nombre: str
    correo: str
    codigo: str

# Esquema para los detalles de la plantilla
class TemplateDetails(BaseModel):
    x: int
    y: int
    font_size: int
    font_family: str
    certificate_path: Optional[str] = None # Guardaremos la ruta del archivo

# Esquema principal que representa una campaña completa en nuestra "base de datos"
class Campaign(BaseModel):
    id: str
    template_details: Optional[TemplateDetails] = None
    students: List[Student] = []
    email_message: Optional[str] = None

# Esquema para la respuesta al crear una campaña
class CampaignCreateResponse(BaseModel):
    campaign_id: str

# Esquema para la solicitud de actualización del mensaje de email
class MessageUpdateRequest(BaseModel):
    message: str = Field(..., min_length=10, description="El cuerpo del correo electrónico.")