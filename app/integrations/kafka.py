from __future__ import annotations

from aiokafka import AIOKafkaProducer

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_producer: AIOKafkaProducer | None = None


def get_kafka_producer() -> AIOKafkaProducer | None:
    return _producer


async def init_kafka(settings: Settings) -> None:
    global _producer
    if not settings.kafka_enabled:
        logger.info("kafka_disabled")
        return

    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=settings.kafka_client_id,
        security_protocol=settings.kafka_security_protocol,
    )
    await _producer.start()
    logger.info(
        "kafka_producer_started",
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )


async def close_kafka() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("kafka_producer_stopped")


async def check_kafka_connection() -> bool:
    if _producer is None:
        return True
    try:
        await _producer.client.check_version()
        return True
    except Exception:
        logger.exception("kafka_health_check_failed")
        return False
