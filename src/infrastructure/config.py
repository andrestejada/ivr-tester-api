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

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_db_url: str
    supabase_jwt_secret: str

    # Twilio (optional - for future integration)
    twilio_account_sid: str = "placeholder"
    twilio_auth_token: str = "placeholder"
    twilio_phone_number: str = "placeholder"

    # Deepgram (optional - for future integration)
    deepgram_api_key: str = "placeholder"


settings = Settings()
