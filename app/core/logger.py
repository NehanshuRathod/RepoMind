from loguru import logger

logger.add(
    "repomind.log",
    rotation="5 MB",
    level="INFO",
    format="{time} | {level} |{message}",
)
