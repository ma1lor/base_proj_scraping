import asyncio

from core.general import General
from core.logger import configure_logging
from settings.config import Settings


async def main() -> None:
    settings = Settings()
    configure_logging(settings)
    app = General(settings)

    async with app.db, app.http:
        await app.db.fetch_one("SELECT 1 AS value")
        app.logger.info("Project is ready")


if __name__ == "__main__":
    asyncio.run(main())
