from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Self

from psycopg import AsyncConnection, AsyncCursor, sql
from psycopg.abc import Params, Query
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from settings.config import Settings


class DBCore:
    def __init__(
        self,
        settings: Settings,
        logger,
        *,
        min_size: int = 1,
        max_size: int = 5,
        timeout: float = 10,
    ):
        self.logger = logger
        self.pool = AsyncConnectionPool(
            kwargs={
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "user": settings.postgres_user,
                "password": settings.postgres_password.get_secret_value(),
                "dbname": settings.postgres_db,
                "connect_timeout": 10,
                "row_factory": dict_row,
            },
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=False,
        )
        self.timeout = timeout

    async def open(self) -> None:
        try:
            await self.pool.open(wait=True, timeout=self.timeout)
        except BaseException:
            # Release resources on startup failure or cancellation.
            await self.pool.close()
            raise
        self.logger.debug("Database pool opened")

    async def close(self) -> None:
        await self.pool.close()
        self.logger.debug("Database pool closed")

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncConnection]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                yield connection

    @asynccontextmanager
    async def _cursor(
        self,
        connection: AsyncConnection | None,
    ) -> AsyncIterator[AsyncCursor]:
        if connection is not None:
            async with connection.cursor(row_factory=dict_row) as cursor:
                yield cursor
        else:
            async with self.pool.connection() as connection:
                async with connection.cursor(row_factory=dict_row) as cursor:
                    yield cursor

    async def fetch_one(
        self,
        query: Query,
        params: Params | None = None,
        *,
        connection: AsyncConnection | None = None,
    ) -> dict[str, Any] | None:
        async with self._cursor(connection) as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchone()

    async def fetch_all(
        self,
        query: Query,
        params: Params | None = None,
        *,
        connection: AsyncConnection | None = None,
    ) -> list[dict[str, Any]]:
        async with self._cursor(connection) as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchall()

    async def execute(
        self,
        query: Query,
        params: Params | None = None,
        *,
        connection: AsyncConnection | None = None,
    ) -> int:
        async with self._cursor(connection) as cursor:
            await cursor.execute(query, params)
            return cursor.rowcount

    async def save_many(
        self,
        rows: list[dict[str, Any]],
        table_name: str,
        *,
        schema: str | None = None,
        connection: AsyncConnection | None = None,
    ) -> int:
        if not rows:
            return 0

        columns = list(rows[0])
        if not columns:
            raise ValueError("Rows must contain at least one column")
        if any(row.keys() != rows[0].keys() for row in rows):
            raise ValueError("All rows must have the same columns")

        table = sql.Identifier(table_name)
        if schema is not None:
            table = sql.Identifier(schema, table_name)

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            table,
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        values = [tuple(row[column] for column in columns) for row in rows]

        async with self._cursor(connection) as cursor:
            await cursor.executemany(query, values)
            return cursor.rowcount
