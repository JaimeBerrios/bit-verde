from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./bitverde.db"
    public_url: str = "https://bitverde.jaimeberrios.com"
    staff_username: str = "staff"
    staff_password: str = ""
    @model_validator(mode="after")
    def secure_production(self):
        if self.environment == "production" and len(self.staff_password) < 16:
            raise ValueError("STAFF_PASSWORD debe tener al menos 16 caracteres en producción")
        return self

settings = Settings()
