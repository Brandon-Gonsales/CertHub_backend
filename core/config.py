import os
from dotenv import load_dotenv
from typing import List

# Carga las variables de entorno desde el archivo .env
load_dotenv()

class Settings:
    # Lee la variable ALLOWED_ORIGINS del entorno. Si no existe, usa una cadena vacía.
    ALLOWED_ORIGINS_STR: str = os.getenv("ALLOWED_ORIGINS", "")
    
    # Procesa la cadena para convertirla en una lista de URLs
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        if not self.ALLOWED_ORIGINS_STR:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS_STR.split(',')]

# Creamos una instancia única de la configuración para ser usada en la app
settings = Settings()