# Engine

FastAPI backend scaffold for the Katana migration engine.

## Local config

Runtime settings are read from [`engine/.env`](./.env).

SMTP-backed notification delivery uses these optional keys:

- `KATANA_SMTP_HOST`
- `KATANA_SMTP_PORT`
- `KATANA_SMTP_USERNAME`
- `KATANA_SMTP_PASSWORD`
- `KATANA_SMTP_FROM_ADDRESS`
- `KATANA_SMTP_USE_TLS`

## Commands

- Start the API: `uvicorn migrations_engine.app:app --reload`
- Run Alembic migrations: `alembic upgrade head`
- Create a new migration: `alembic revision --autogenerate -m "message"`

## Layout

- `src/migrations_engine/` contains the application code
- `migrations/` contains Alembic configuration and revisions
