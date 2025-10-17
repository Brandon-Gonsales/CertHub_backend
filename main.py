from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# La línea clave a cambiar es esta:
from modules.campaigns.router import router as campaigns_router
from core.config import settings

app = FastAPI(
    title="API de Campañas",
    description="Backend para la gestión de campañas de certificados.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ahora 'campaigns_router' es el objeto APIRouter, que es lo correcto
app.include_router(campaigns_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}