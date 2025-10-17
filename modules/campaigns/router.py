from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, status, BackgroundTasks
from . import service
from .schemas import CampaignCreateResponse, MessageUpdateRequest, ActivateCampaignRequest

# Creamos un "router" para agrupar todos los endpoints de campañas
router = APIRouter(
    prefix="/campaigns",
    tags=["Campaigns"] # Etiqueta para la documentación de Swagger/OpenAPI
)

@router.post("/", response_model=CampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_campaign():
    """
    Crea una nueva campaña vacía.
    Devuelve el ID único de la campaña recién creada.
    """
    campaign_id = service.create_new_campaign()
    return {"campaign_id": campaign_id}

@router.put("/{campaign_id}/template")
def update_template(
    campaign_id: str,
    x: int = Form(...),
    y: int = Form(...),
    font_size: int = Form(...),
    font_family: str = Form(...),
    certificate: UploadFile = File(...)
):
    """
    Actualiza la información de la plantilla para una campaña.
    Recibe los datos de la plantilla y el archivo del certificado (PNG o PDF).
    """
    service.update_campaign_template(campaign_id, x, y, font_size, font_family, certificate)
    return {"message": "Plantilla de la campaña actualizada correctamente."}

@router.put("/{campaign_id}/students")
def update_students(campaign_id: str, students_file: UploadFile = File(...)):
    """
    Actualiza la lista de estudiantes desde un archivo Excel.
    El Excel debe tener las columnas "nombres" y "correo".
    Genera y asigna un código alfanumérico único de 8 dígitos para cada estudiante.
    """
    processed_count = service.update_campaign_students(campaign_id, students_file)
    return {"message": f"Se procesaron y añadieron {processed_count} estudiantes."}
    
@router.put("/{campaign_id}/message")
def update_message(campaign_id: str, payload: MessageUpdateRequest):
    """
    Actualiza el cuerpo del mensaje del correo electrónico para una campaña.
    """
    service.update_campaign_message(campaign_id, payload.message)
    return {"message": "Mensaje de la campaña actualizado correctamente."}

@router.post("/{campaign_id}/activate", status_code=status.HTTP_202_ACCEPTED)
def activate_campaign(
    campaign_id: str,
    payload: ActivateCampaignRequest,
    background_tasks: BackgroundTasks # FastAPI inyecta este objeto automáticamente
):
    """
    Activa una campaña, iniciando el proceso de envío de correos a todos los
    estudiantes registrados. Este proceso se ejecuta en segundo plano.
    """
    return service.activate_campaign_and_send_emails(
        campaign_id, 
        payload.fixed_url, 
        background_tasks
    )