import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

from app.core.config import settings

logger = logging.getLogger(__name__)

_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",                  # wait for all replicas to acknowledge
            retries=3,
            max_block_ms=10000,          # 10s timeout if Kafka is unavailable
        )
    return _producer


def send_extraction_job(
    document_id: str,
    application_id: str,
    doc_type: str,
    file_path: str,
) -> bool:
    """
    Publish an extraction job to the Kafka topic.
    Returns True on success, False on failure.
    """
    message = {
        "document_id": document_id,
        "application_id": application_id,
        "doc_type": doc_type,
        "file_path": file_path,
    }
    try:
        producer = get_producer()
        future = producer.send(
            topic=settings.kafka_extraction_topic,
            key=application_id,          # partition by application_id
            value=message,
        )
        producer.flush(timeout=5)
        record_metadata = future.get(timeout=5)
        logger.info(
            f"Extraction job sent — topic={record_metadata.topic} "
            f"partition={record_metadata.partition} "
            f"offset={record_metadata.offset} "
            f"document_id={document_id}"
        )
        return True
    except KafkaError as e:
        logger.error(f"Failed to send extraction job for document {document_id}: {e}")
        return False


def close_producer():
    global _producer
    if _producer:
        _producer.close()
        _producer = None
