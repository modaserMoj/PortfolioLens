from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./portfoliolens.db"
    OPENAI_API_KEY: str = ""
    BRAVE_API_KEY: str = ""
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    RISK_FREE_RATE: float = 0.05
    BENCHMARK_TICKER: str = "SPY"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
