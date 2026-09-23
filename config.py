from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SARVAM_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/test-ledger"
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()