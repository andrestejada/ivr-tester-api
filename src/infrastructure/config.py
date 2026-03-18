from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_port: int = 8000
    base_url: str  # Requerida en .env (ej: http://localhost:8000, ngrok tunnel en dev, https://api.example.com en prod)

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_db_url: str
    supabase_jwt_secret: str

    # Twilio
    twilio_account_sid: str = "placeholder"
    twilio_auth_token: str = "placeholder"
    twilio_phone_number: str = "placeholder"

    # Deepgram (ASR streaming)
    deepgram_api_key: str  # Requerida para habilitar el adaptador ASR en tiempo real


settings = Settings()
