from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "REPOMIND"
    DEBUG: bool = True

    class config:
        env_file = ".env"

Settings = Settings()