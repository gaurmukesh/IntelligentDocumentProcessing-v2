"""
Kafka Consumer — runs as a separate process.

Start with:
    python -m app.services.kafka_consumer

Consumes messages from the 'document-extraction' topic,
runs GPT-4o extraction, and saves results to SQLite.
"""

import asyncio
import json
import logging
import signal
import sys

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from app.core.config import settings
from app.models.document import DocumentType

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received — stopping consumer...")
    running = False


async def process_message(message: dict):
    """Extract document data and save result to DB."""
    from app.models.database import AsyncSessionLocal
    from app.models.document import Document, DocumentStatus, ExtractionResult
    from app.services.extractor import extract_document
    from sqlalchemy import select

    document_id = message["document_id"]
    application_id = message["application_id"]
    doc_type = DocumentType(message["doc_type"])
    file_path = message["file_path"]

    async with AsyncSessionLocal() as db:
        # Mark as EXTRACTING
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            logger.warning(f"Document {document_id} not found in DB — skipping")
            return

        doc.status = DocumentStatus.EXTRACTING
        await db.commit()

        try:
            from app.services.storage import download_to_temp
            import os
            local_path = download_to_temp(file_path)
            extracted_data, confidence = extract_document(local_path, doc_type)
            # Clean up temp file if it was downloaded from S3
            if local_path != file_path:
                try:
                    os.unlink(local_path)
                except OSError:
                    pass
            extraction = ExtractionResult(
                document_id=document_id,
                application_id=application_id,
                doc_type=doc_type,
                extracted_data=json.dumps(extracted_data),
                confidence_score=confidence,
            )
            doc.status = DocumentStatus.EXTRACTED
            logger.info(
                f"Extraction complete — document_id={document_id} "
                f"confidence={confidence}"
            )
        except Exception as e:
            extraction = ExtractionResult(
                document_id=document_id,
                application_id=application_id,
                doc_type=doc_type,
                error_message=str(e),
            )
            doc.status = DocumentStatus.FAILED
            logger.error(f"Extraction failed — document_id={document_id} error={e}")

        db.add(extraction)
        await db.commit()


def run_consumer():
    """Main consumer loop."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(f"Starting Kafka consumer — topic={settings.kafka_extraction_topic} "
                f"group={settings.kafka_consumer_group} "
                f"brokers={settings.kafka_bootstrap_servers}")

    consumer = KafkaConsumer(
        settings.kafka_extraction_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",    # process from beginning if no offset exists
        enable_auto_commit=False,        # manual commit after processing
        max_poll_records=5,              # process 5 messages at a time
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )

    logger.info("Consumer ready — waiting for messages...")

    while running:
        try:
            records = consumer.poll(timeout_ms=1000)
            for topic_partition, messages in records.items():
                for msg in messages:
                    logger.info(
                        f"Received message — partition={msg.partition} "
                        f"offset={msg.offset} key={msg.key}"
                    )
                    try:
                        asyncio.run(process_message(msg.value))
                        consumer.commit()   # commit only after successful processing
                    except Exception as e:
                        logger.error(f"Failed to process message: {e}")
                        # Do not commit — message will be reprocessed on restart
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")

    logger.info("Consumer stopped.")
    consumer.close()


if __name__ == "__main__":
    run_consumer()
