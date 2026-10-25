from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = Field(default="Saathi AI - Cybercrime Reporting Assistant")
    APP_ENV: str = Field(default="development")
    APP_PORT: int = Field(default=8000)
    SECRET_KEY: str = Field(default="dev_secret_key_change_in_production_saathi_2026")

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://samaran_user:samaran_dev_pass_2026@127.0.0.1:5433/samaran"
    )

    # Ollama Local LLM
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_MODEL: str = Field(default="qwen3:8b")

    # Faster-Whisper
    WHISPER_MODEL_SIZE: str = Field(default="base")
    WHISPER_DEVICE: str = Field(default="cpu")
    WHISPER_COMPUTE_TYPE: str = Field(default="int8")

    # WhatsApp Cloud API & Meta Configuration
    WHATSAPP_VERIFY_TOKEN: str = Field(default="samaran_dev_verify_token_2026")
    WHATSAPP_ACCESS_TOKEN: str = Field(default="")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(default="")
    META_APP_SECRET: str = Field(default="")
    WHATSAPP_APP_SECRET: str = Field(default="")
    WHATSAPP_API_VERSION: str = Field(default="v21.0")

    @property
    def effective_app_secret(self) -> str:
        """Returns META_APP_SECRET or WHATSAPP_APP_SECRET interchangeably."""
        return self.META_APP_SECRET or self.WHATSAPP_APP_SECRET

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
