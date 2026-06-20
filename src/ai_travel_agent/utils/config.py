"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API keys
    anthropic_api_key: str = ""
    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    openweathermap_api_key: str = "41eef9a9f37a46b699368566ecdcc270"
    serper_api_key: str = "0b1bc5bd2f38d842c7c889b8ba81cde7b6f639b3"

    # Redis
    redis_url: str = "redis://localhost:6379"
    use_fake_redis: bool = False  # set True for local dev without Redis server

    # Cache TTLs (seconds)
    cache_ttl_flights: int = 3600
    cache_ttl_hotels: int = 3600
    cache_ttl_weather: int = 1800

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
