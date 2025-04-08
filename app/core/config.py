from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ticket Assistant API"
    VERSION: str = "1.0.0"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE")
    MODEL: str = os.getenv("MODEL", "gpt-3.5-turbo")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    class Config:
        case_sensitive = True

settings = Settings()