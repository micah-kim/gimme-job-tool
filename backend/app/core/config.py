from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"

    # Database
    database_url: str = "sqlite+aiosqlite:///./gimme_job.db"

    # Application
    max_applications_per_run: int = 10
    fetch_interval_hours: int = 6
    min_relevance_score: int = 60
    dry_run: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
