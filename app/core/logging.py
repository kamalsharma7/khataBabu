from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from app.core.config import Settings

# khataBabu/ (project root containing app/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def resolve_log_file_path(settings: Settings) -> Path:
    raw = Path(settings.log_file)
    if raw.is_absolute():
        return raw
    return PROJECT_ROOT / raw


def setup_logging(settings: Settings) -> Path:
    """Configure structlog + stdlib logging; all records go to logs/kblogs.log (and optional console)."""
    log_path = resolve_log_file_path(settings)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if settings.log_to_console:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    for noisy in ("sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if settings.db_echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    structlog.get_logger(__name__).info(
        "logging_configured",
        log_file=str(log_path),
        log_level=settings.log_level.upper(),
        log_json=settings.log_json,
        log_to_console=settings.log_to_console,
    )
    return log_path


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
