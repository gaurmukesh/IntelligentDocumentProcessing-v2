from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/idp.db"

    # Storage — local dev uses upload_dir; production uses S3-compatible Object Storage
    upload_dir: str = "./data/uploads"
    s3_endpoint_url: str = ""          # e.g. https://sgp1.digitaloceanspaces.com (Lightsail uses AWS S3 natively)
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "ap-south-1"
    s3_bucket_name: str = "idp-uploads"

    # Vector DB (Qdrant)
    # Local dev: uses qdrant_path (file-based). Production: uses qdrant_host + qdrant_port (server mode).
    qdrant_path: str = "./qdrant_db"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
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
