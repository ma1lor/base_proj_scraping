from typing import Any
from uuid import uuid4

from loguru import logger

from core.db.postgres import DBCore
from core.http_client import HttpClient
from settings.config import Settings


class General:
    service_name = "general"
    db_class: type[DBCore] = DBCore

    def __init__(
        self,
        settings: Settings,
        db_class: type[DBCore] | None = None,
        *,
        http_options: dict[str, Any] | None = None,
    ):
        self.settings = settings
        self.project_name = settings.project_name
        self.task_id = str(uuid4())
        self.logger = logger.bind(
            project=self.project_name,
            service=self.service_name,
            component="service",
            task_id=self.task_id,
        )

        if db_class is None:
            db_class = self.db_class

        self.db = db_class(
            settings=settings,
            logger=self.logger.bind(component="db"),
        )
        self.http = HttpClient(
            logger=self.logger.bind(component="http"),
            **(http_options or {}),
        )
