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

    # Faster-Whisper Local Speech-to-Text
    WHISPER_MODEL_SIZE: str = Field(default="medium")  # medium by default, supports large-v3
    WHISPER_DEVICE: str = Field(default="cpu")
    WHISPER_COMPUTE_TYPE: str = Field(default="int8")
    WHISPER_BEAM_SIZE: int = Field(default=5)
    WHISPER_VAD_FILTER: bool = Field(default=True)
    WHISPER_FALLBACK_MODEL_SIZE: str = Field(default="tiny")

    # Local Translation Configuration
    TRANSLATION_MODEL: str = Field(default="qwen2.5:3b")
    TRANSLATION_ENGINE: str = Field(default="ollama")  # ollama (primary for contextual Indic translation), or argos
    TRANSLATION_TIMEOUT_SECONDS: float = Field(default=30.0)


    # WhatsApp Cloud API & Meta Configuration
    WHATSAPP_VERIFY_TOKEN: str = Field(default="samaran_dev_verify_token_2026")
    WHATSAPP_ACCESS_TOKEN: str = Field(default="")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(default="")
    META_APP_SECRET: str = Field(default="")
    WHATSAPP_APP_SECRET: str = Field(default="")
    WHATSAPP_API_VERSION: str = Field(default="v21.0")

    # Voice Recording & Audio Upload Configuration
    VOICE_UPLOAD_DIR: str = Field(default="backend/storage/voice_notes")
    MAX_AUDIO_SIZE_BYTES: int = Field(default=5 * 1024 * 1024)  # 5 MB
    MAX_AUDIO_DURATION_SECONDS: float = Field(default=120.0)    # 2 minutes (120s)
    VOICE_RETENTION_HOURS: int = Field(default=24)              # 24h temporary storage

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
