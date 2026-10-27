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
    WHISPER_MODEL_SIZE: str = Field(default="small")  # small for fast responsive local inference; supports medium, large-v3
    WHISPER_DEVICE: str = Field(default="cpu")
    WHISPER_COMPUTE_TYPE: str = Field(default="int8")
    WHISPER_BEAM_SIZE: int = Field(default=1)         # beam_size=1 gives 3-5x faster decoding with high accuracy
    WHISPER_VAD_FILTER: bool = Field(default=True)
    WHISPER_FALLBACK_MODEL_SIZE: str = Field(default="tiny")
    WHISPER_CPU_THREADS: int = Field(default=4)

    # Local Translation Configuration
    TRANSLATION_MODEL: str = Field(default="qwen2.5:3b")
    TRANSLATION_ENGINE: str = Field(default="ollama")  # ollama (primary for contextual Indic translation), or argos
    TRANSLATION_TIMEOUT_SECONDS: float = Field(default=30.0)

    # Complaint Extraction Configuration (Phase 4)
    EXTRACTION_MODEL: str = Field(default="qwen2.5:3b")
    EXTRACTION_TIMEOUT_SECONDS: float = Field(default=20.0)
    EXTRACTION_MAX_RETRIES: int = Field(default=2)
    COMPLAINT_TOKEN_EXPIRY_HOURS: int = Field(default=24)


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
    MAX_CONCURRENT_TRANSCRIPTIONS: int = Field(default=2)       # Guard against resource exhaustion

    # Rate Limiting Configuration (Phase 7 Security Hardening)
    RATE_LIMIT_VOICE_UPLOAD: str = Field(default="15/minute")
    RATE_LIMIT_VOICE_STATUS: str = Field(default="180/minute")
    RATE_LIMIT_VOICE_TRANSLATE: str = Field(default="30/minute")
    RATE_LIMIT_COMPLAINT_READ: str = Field(default="120/minute")
    RATE_LIMIT_COMPLAINT_WRITE: str = Field(default="30/minute")
    RATE_LIMIT_COMPLAINT_CONFIRM: str = Field(default="15/minute")
    RATE_LIMIT_ACTIONS: str = Field(default="45/minute")
    RATE_LIMIT_PUBLIC_LOOKUP: str = Field(default="10/minute")
    TRUSTED_PROXIES: str = Field(default="")  # Comma-separated list of trusted proxy IPs

    # Transcript & Complaint Retention Policy (Phase 7)
    TRANSCRIPT_RETENTION_HOURS: int = Field(default=24)
    UNCONFIRMED_COMPLAINT_RETENTION_HOURS: int = Field(default=24)
    CANCELLED_COMPLAINT_RETENTION_HOURS: int = Field(default=48)
    CONFIRMED_COMPLAINT_RETENTION_DAYS: int = Field(default=30)
    ABANDONED_AUDIO_CLEANUP_HOURS: int = Field(default=1)

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
