from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Application configuration
    APP_NAME: str = "UNO Game Server"
    DEBUG: bool = True
    
    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Game rules
    DISCONNECT_TIMEOUT_SECONDS: int = 60
    
    # Modern Pydantic configuration settings
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()