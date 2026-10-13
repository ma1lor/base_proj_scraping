# Async Python Project Template

A small starting point for projects that use PostgreSQL and HTTP requests.
It includes Pydantic Settings, Loguru, Psycopg 3, curl_cffi, Docker Compose,
and a standalone Bash project initializer.

## Requirements

- macOS or Linux with Bash and Git.
- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Docker with Docker Compose for running PostgreSQL.
- Python 3.13, which uv can download automatically.

Docker must be running before starting PostgreSQL. It is not needed to generate
the project. The first dependency installation needs internet access unless
the required packages and Python are already cached.

## Install the init_project command

From this repository:

```bash
mkdir -p "$HOME/.local/bin"
install -m 755 init_project "$HOME/.local/bin/init_project"
```

Add the following line to `~/.zshrc` for Zsh or `~/.bashrc` for Bash:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Reload your shell configuration, then check which command will run:

```bash
source ~/.zshrc  # For Bash, use: source ~/.bashrc
command -v init_project
```

The expected path is your home directory followed by `.local/bin/init_project`.
If `/usr/local/bin/init_project` contains an older version, placing `.local/bin`
first in PATH makes the new version take precedence. Open a new terminal if
your shell still resolves the old command. Bash login shells must also load
`~/.bashrc` from their login configuration if they do not already do so.

The installed file is self-contained: it does not need this repository beside
it and does not download a template from GitHub.

## Generate a project

Create a new directory:

```bash
init_project company_scraper
cd company_scraper
```

Or initialize an existing empty directory:

```bash
mkdir company_scraper
cd company_scraper
init_project
```

Paths containing spaces are supported when quoted:

```bash
init_project "$HOME/My Projects/company_scraper"
```

The directory name becomes the project name. Letters are converted to lowercase;
spaces and hyphens become underscores. The result must start with a letter,
contain only lowercase letters, digits and underscores, and have at most
63 characters.

The initializer creates the source files, configuration, this README, and a copy
of itself. It installs dependencies with uv, creates `.env` with a random local
PostgreSQL password, and initializes Git without committing or adding a remote.
An existing `.git` directory is allowed; any other existing entry causes the
initializer to stop before writing files. Re-running it on a generated project
does not overwrite your code or settings.

If initialization fails after files have been written, they remain available
for inspection. For a dependency installation failure, fix the cause and run
`uv sync --python 3.13` in the generated directory. If `.env` was not created,
copy `.env.example` to `.env` and set a password before starting PostgreSQL.

## Run a generated project or this template

For a fresh clone of this repository, first run:

```bash
cp .env.example .env
# Edit .env: set PROJECT_NAME and POSTGRES_PASSWORD.
uv sync --locked
```

Generated projects already have `.env` and an installed environment.

```bash
docker compose up -d --wait
uv run python src/main.py
```

The starter checks PostgreSQL with `SELECT 1`, logs `Project is ready`, and closes
its resources. It does not create application tables or make external HTTP
requests. Replace its body with your workflow.

Settings reads `.env` from the project root. Environment variables take
precedence. Run Compose commands from the root so Python and Compose read the
same file. `PROJECT_NAME` identifies the Compose project, PostgreSQL database,
and project context in logs. There is no separate `POSTGRES_DB` setting.

`POSTGRES_HOST=localhost` is for Python running on the host. `POSTGRES_PORT`
controls the published PostgreSQL port; choose a different port when running
multiple projects. PostgreSQL itself listens on port 5432 inside its container.

Database data lives in a Compose volume. Changing `PROJECT_NAME` selects a
different default volume; it does not rename or migrate an existing database.
Changing the password in `.env` does not update a role in an initialized volume.
`docker compose down` stops the stack and keeps the volume.

## Where code belongs

```text
.
├── init_project              # Standalone project generator
├── pyproject.toml            # Python requirements and dependencies
├── uv.lock                   # Resolved dependency versions
├── .env.example              # Shareable configuration example
├── .env                      # Local configuration; excluded from Git
├── docker-compose.yml        # PostgreSQL service and persistent volume
└── src/
    ├── main.py               # Entry point: setup, resource lifetime, workflow
    ├── pipeline.py           # Optional coordination of workflow stages
    ├── core/
    │   ├── general.py        # Shared component initialization
    │   ├── logger.py         # Loguru configuration
    │   ├── http_client.py    # Shared HTTP behavior
    │   └── db/postgres.py    # DBCore: connections and SQL execution
    ├── db/                   # Project-specific subclasses and SQL methods
    ├── services/             # Business logic using DB and HTTP methods
    ├── settings/config.py    # Typed environment configuration
    ├── models/               # Project-specific data models, when needed
    ├── sql/                  # SQL files for your application's schema/queries
    ├── utils/snippets.py     # Existing optional utility functions
    ├── recourses/            # Existing desktop/mobile user-agent JSON files
    └── logs/                 # Runtime logs; excluded from Git
```

Keep connection handling in `core`, project queries in `db`, and business rules
in `services`. Empty directories are placeholders, not requirements to create
more layers. The existing `recourses` spelling is preserved.

## Write project-specific database queries

Create `src/db/companies.py`:

```python
from core.db.postgres import DBCore


class CompanyDB(DBCore):
    async def get_pending_companies(self):
        return await self.fetch_all(
            "SELECT id, url FROM companies WHERE status = %s",
            ("pending",),
        )

    async def mark_done(self, company_id):
        return await self.execute(
            "UPDATE companies SET status = %s WHERE id = %s",
            ("done", company_id),
        )
```

`fetch_one` returns a dictionary or `None`; `fetch_all` returns a list of
dictionaries. `execute` returns the driver's row count, which may be `-1` for
commands without an applicable count. Use `fetch_one`/`fetch_all` for SQL with
`RETURNING`. Pass SQL values separately from the query; do not interpolate them
with f-strings.

For batch inserts:

```python
count = await db.save_many(
    [{"name": "First"}, {"name": "Second"}],
    table_name="companies",
)
```

All rows must have the same keys. An empty batch returns `0`. Table and column
names are quoted by Psycopg. For another schema, pass `schema="schema_name"`.
The method does not implement upsert or create tables.

Each standalone method commits on success and rolls back on error. For several
operations that must succeed together, use `db.transaction()` and pass its
`connection` to every related call:

```python
async with db.transaction() as connection:
    await db.execute(first_query, first_params, connection=connection)
    await db.execute(second_query, second_params, connection=connection)
```

Omitting `connection=` executes that call separately. Exceptions propagate to
the caller. Database writes are not automatically retried. The default pool
holds 1–5 connections. Its acquisition/startup timeout and the connection
timeout are 10 seconds; SQL execution has no configured time limit.

## Write business logic

Create `src/services/companies.py`:

```python
from core.general import General
from db.companies import CompanyDB


class CompanyService(General):
    service_name = "companies"
    db_class = CompanyDB

    async def run(self):
        companies = await self.db.get_pending_companies()

        for company in companies:
            response = await self.http.get(company["url"])
            self.logger.info(
                "Fetched company {}: status={}",
                company["id"],
                response.status_code,
            )
            await self.db.mark_done(company["id"])
```

The example expects an existing `companies` table with `id`, `url`, and `status`
columns. Schema creation is your project's responsibility.

In `src/main.py`, configure logging once and manage resources explicitly:

```python
import asyncio

from core.logger import configure_logging
from services.companies import CompanyService
from settings.config import Settings


async def main():
    settings = Settings()
    configure_logging(settings)
    service = CompanyService(settings, http_options={"timeout": 60})

    async with service.db, service.http:
        await service.run()


if __name__ == "__main__":
    asyncio.run(main())
```

`General` only stores settings, binds logger context, and creates your DB and
HTTP objects. It does not run the script, define `run()`, configure global
logging, or open network connections. Each instance has its own `task_id`, DB
pool, and HTTP client. `async with` opens the clients and closes them on exit.
Create a new instance for another run after closing its resources.

## HTTP requests and workers

```python
response = await service.http.get(url, params={"page": 1})
data = response.json()

response = await service.http.post(url, json={"name": "Example"})
response = await service.http.get(url, raise_for_status=False)
```

The client returns curl_cffi's `Response`. Use `.text`, `.content`, `.headers`,
`.status_code`, or `.json()` as needed. Session cookies persist between calls.
Default settings: 30-second timeout per attempt, 10 concurrent requests, TLS
verification enabled, and at most three attempts for GET/HEAD on selected
connection errors, timeouts, or statuses 429/502/503/504. POST is not retried.
`Retry-After` is respected up to 60 seconds. Total time can exceed the request
timeout because of queueing and retries. HTTP errors raise by default.

Pass `headers`, `cookies`, `proxy`, or `impersonate` through `http_options` when
creating the service. Request arguments can override session defaults.
`proxy=None` on a request explicitly disables its proxy; proxy environment
variables are not used. There is no automatic proxy or user-agent rotation.
For streaming, use the opened `service.http.session.stream()` directly.

Separate workers can own separate HTTP sessions:

```python
from core.http_client import HttpClient


async def worker(urls, logger):
    async with HttpClient(logger=logger) as http:
        for url in urls:
            response = await http.get(url)
            # Process the response.


await asyncio.gather(
    worker(first_urls, service.logger.bind(component="worker_1")),
    worker(second_urls, service.logger.bind(component="worker_2")),
)
```

The final `await` belongs inside an async function. Workers run concurrently;
requests within each worker above are sequential. Each HTTP client has its own
concurrency limit. Wait for all worker tasks before closing shared resources.

## Logging and optional utilities

Loguru writes INFO and above to the console and DEBUG and above to
`src/logs/app.log`. Files rotate at 10 MB with seven-day retention. Context
includes project, service, component, and task ID. `logger.bind()` adds context;
it does not create another log file. Components do not configure handlers.

Do not include credentials, cookies, full URLs with secrets, or response bodies
in your own log messages. `diagnose=False` disables local-variable dumps in
tracebacks; it does not sanitize arbitrary messages or exception text.

`utils/snippets.py` is an existing optional collection, separate from the core.
Some functions require pandas, lxml, or html5lib, which are not installed by
default. Add only the libraries your code uses with `uv add`. Some legacy
helpers return exception objects instead of raising them; inspect their
behavior before using them. User-agent JSON files are optional static data and
may contain old browser versions.

