import json
import sys
from datetime import datetime, timezone

from loguru import logger


class JSONSink:
    def write(self, message) -> None:
        record = message.record
        payload = {
            "timestamp": record["time"].astimezone(timezone.utc).isoformat(),
            "level": record["level"].name,
            "logger": "repomind",
            "message": record["message"],
        }
        payload.update(record["extra"])
        exception = record["exception"]
        if exception is not None:
            payload["exception"] = str(exception)
        sys.stdout.write(json.dumps(payload) + "\n")


logger.remove()
logger.add(
    JSONSink(),
    level="INFO",
    format="{message}",
    colorize=False,
)


def log_event(event: str, **fields) -> None:
    logger.bind(event=event, **fields).info(event)
