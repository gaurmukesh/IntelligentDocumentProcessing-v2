from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/idp.db"

    # Storage
    upload_dir: str = "./data/uploads"

    # Vector DB (Qdrant)
    qdrant_path: str = "./qdrant_db"
    qdrant_collection_name: str = "idp_knowledge_base"

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Spring Boot ERP
    erp_base_url: str = "http://localhost:8080"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_extraction_topic: str = "document-extraction"
    kafka_consumer_group: str = "idp-extraction-group"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self):
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.qdrant_path).mkdir(parents=True, exist_ok=True)


settings = Settings()
