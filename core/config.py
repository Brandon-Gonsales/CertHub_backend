from pydantic_settings import BaseSettings
from typing import List, Union

class Settings(BaseSettings):
    ALLOWED_ORIGINS: Union[List[str], str] = []

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int = 587
    MAIL_SERVER: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_FROM_NAME: str

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

if isinstance(settings.ALLOWED_ORIGINS, str):
    settings.ALLOWED_ORIGINS = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
