"""
Clarion — RabbitMQ Publisher
"""
import os
import json
import aio_pika
from loguru import logger

# Sử dụng chung biến với CELERY_BROKER_URL từ .env cho tiện
RABBITMQ_URL = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
EXCHANGE_NAME = "clarion_events"

async def get_rabbitmq_connection():
    return await aio_pika.connect_robust(RABBITMQ_URL)

async def publish_event(routing_key: str, payload: dict):
    """Publish an event to the clarion_events topic exchange."""
    try:
        connection = await get_rabbitmq_connection()
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                EXCHANGE_NAME, 
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            message_body = json.dumps(payload).encode()
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await exchange.publish(message, routing_key=routing_key)
            logger.info(f"[RabbitMQ] Published event: {routing_key}")
    except Exception as e:
        logger.error(f"[RabbitMQ] Error publishing event {routing_key}: {e}")
        raise
