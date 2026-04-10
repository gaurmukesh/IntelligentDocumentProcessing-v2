"""
Unit tests for Phase 0 — Configuration & Settings

Run with:
    cd backend-fastapi
    source venv/bin/activate
    pytest tests/test_config.py -v
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestSettings:

    def test_settings_load_with_required_fields(self):
        """Settings must load without error when OPENAI_API_KEY is set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            from importlib import reload
            import app.core.config as cfg_module
            reload(cfg_module)
            settings = cfg_module.Settings()
            assert settings.openai_api_key == "sk-test-key"

    def test_default_openai_model(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.openai_model == "gpt-4o"

    def test_default_embedding_model(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.openai_embedding_model == "text-embedding-3-small"

    def test_default_upload_dir(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.upload_dir == "./data/uploads"

    def test_default_app_port(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.app_port == 8000

    def test_default_kafka_topic(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.kafka_extraction_topic == "document-extraction"

    def test_default_kafka_consumer_group(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            assert s.kafka_consumer_group == "idp-extraction-group"

    def test_env_override_model(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4-turbo"
        }):
            from app.core.config import Settings
            s = Settings()
            assert s.openai_model == "gpt-4-turbo"

    def test_ensure_dirs_creates_upload_dir(self, tmp_path):
        """ensure_dirs() must create upload and qdrant directories."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            s.upload_dir = str(tmp_path / "uploads")
            s.qdrant_path = str(tmp_path / "qdrant_db")
            s.ensure_dirs()
            assert Path(s.upload_dir).exists()
            assert Path(s.qdrant_path).exists()

    def test_ensure_dirs_idempotent(self, tmp_path):
        """Calling ensure_dirs() twice should not raise an error."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            from app.core.config import Settings
            s = Settings()
            s.upload_dir = str(tmp_path / "uploads")
            s.qdrant_path = str(tmp_path / "qdrant_db")
            s.ensure_dirs()
            s.ensure_dirs()   # second call — should not fail
            assert Path(s.upload_dir).exists()
