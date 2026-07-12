"""
RabbitMQ consumer for notification-related events.

Routing keys consumed:
  - notification.trigger → generic notification forwarded to dispatcher
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import aio_pika
from jobcopilot_shared.events import (
    NOTIFICATION_TRIGGER_KEY,
    NotificationTriggerEvent,
)

from jobcopilot_notification.config import settings
from jobcopilot_notification.services.dispatcher import dispatch_standalone

log = logging.getLogger(__name__)

_EXCHANGE = settings.rabbitmq_exchange
_QUEUE = "notification.events"
_ROUTING_KEYS = [NOTIFICATION_TRIGGER_KEY]


async def _handle_notification_trigger(body: dict[str, Any]) -> None:
    event = NotificationTriggerEvent.model_validate(body)
    await dispatch_standalone(
        tenant_id=uuid.UUID(event.tenant_id),
        user_id=uuid.UUID(event.user_id),
        type=event.type,
        title=event.title,
        body=event.body,
        channels=event.channels,
        metadata=event.metadata,
    )


_HANDLERS = {
    NOTIFICATION_TRIGGER_KEY: _handle_notification_trigger,
}


async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        routing_key = message.routing_key or ""
        try:
            body = json.loads(message.body.decode())
            handler = _HANDLERS.get(routing_key)
            if handler:
                await handler(body)
            else:
                log.debug("consumer_routing_key_ignored", extra={"key": routing_key})
        except Exception as exc:
            log.error(
                "consumer_message_failed",
                extra={"routing_key": routing_key, "error": str(exc)},
            )


async def start_consumer() -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
                )
                queue = await channel.declare_queue(_QUEUE, durable=True)
                for key in _ROUTING_KEYS:
                    await queue.bind(exchange, routing_key=key)

                log.info("consumer_started", extra={"queue": _QUEUE, "keys": _ROUTING_KEYS})
                await queue.consume(_on_message)
                await asyncio.Future()
        except Exception as exc:
            log.error("consumer_connection_lost", extra={"error": str(exc)})
            await asyncio.sleep(5)


def start_consumer_background() -> asyncio.Task[None]:
    return asyncio.ensure_future(start_consumer())
