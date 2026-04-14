"""
Storage abstraction — local disk in dev, Lightsail Object Storage (S3) in production.

Local dev  : files saved to  settings.upload_dir / <key>
Production : files stored in Lightsail Object Storage bucket (S3-compatible API)
"""

import tempfile
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def upload_file(file_bytes: bytes, key: str) -> str:
    """
    Save file bytes to storage.
    Returns the storage key (S3 key in prod, absolute local path in dev).
    """
    if settings.app_env == "production":
        _s3().put_object(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Body=file_bytes,
        )
        logger.info(f"Uploaded to S3: {key}")
        return key
    else:
        local_path = Path(settings.upload_dir) / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_bytes)
        logger.info(f"Saved locally: {local_path}")
        return str(local_path)


def download_to_temp(file_ref: str) -> str:
    """
    Get a local file path ready for the extractor.
    In production: downloads from S3 to a temp file.
    In dev: returns the path as-is (already local).
    Returns the local file path.
    """
    if settings.app_env == "production":
        suffix = Path(file_ref).suffix or ".tmp"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            _s3().download_fileobj(settings.s3_bucket_name, file_ref, tmp)
        except ClientError as e:
            logger.error(f"Failed to download {file_ref} from S3: {e}")
            raise
        finally:
            tmp.close()
        return tmp.name
    else:
        return file_ref


def delete_file(file_ref: str):
    """Delete a file from storage (best-effort)."""
    try:
        if settings.app_env == "production":
            _s3().delete_object(Bucket=settings.s3_bucket_name, Key=file_ref)
        else:
            Path(file_ref).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Could not delete {file_ref}: {e}")
