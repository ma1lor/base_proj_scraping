import sys

from loguru import logger

from settings.config import Settings


def configure_logging(settings: Settings) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{extra[project]} | {extra[service]} | "
        "{extra[component]} | {extra[task_id]} | {message}"
    )

    logger.remove()
    logger.configure(
        extra={
            "project": settings.project_name,
            "service": "-",
            "component": "-",
            "task_id": "-",
        }
    )
    logger.add(
        sys.stderr,
        level="INFO",
        format=log_format,
        diagnose=False,
        backtrace=False,
    )
    logger.add(
        settings.logs_dir / "app.log",
        level="DEBUG",
        format=log_format,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
        diagnose=False,
        backtrace=False,
    )
