"""
ai_travel_agent/utils/logging_setup.py — Week 19

Adds structured logging with correlation IDs on top of your existing
utils/logger.py — that file's get_logger() keeps working everywhere
it's already used (base.py, conflict_resolver.py, etc.); this module
only adds a JSON-structured path + a way to attach a session/thread_id
to every log line for a given request, for debugging concurrent
planning sessions.

Add to pyproject.toml:
    structlog = ">=24.1.0,<25.0.0"

Usage in api/main.py (see WEEK17_18_19_GUIDE.md for the exact patch):
    from ai_travel_agent.utils.logging_setup import configure_structlog, bind_session
    configure_structlog()
    ...
    # inside /plan, /ws/plan, etc.
    bind_session(session_id=session_id)
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_structlog(json_output: bool = True) -> None:
    """Call once at app startup. Routes stdlib logging.getLogger(...) calls
    (i.e. everything using your existing get_logger()) through the same
    structlog processors, so you get one consistent log format instead of
    two competing ones."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def bind_session(**kwargs) -> None:
    """Attach fields (session_id, job_id, destination, ...) to every log
    line emitted for the current async context — call at the top of
    /plan, /refine, and inside ws_plan right after session_id is created."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_session_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_struct_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
