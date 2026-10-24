"""Resolve database settings without ever creating a production SQLite fallback."""

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def _env_value(environ, key, default=""):
    value = environ.get(key, default)
    if value is None:
        return ""
    return str(value).strip()


def database_config(environ, base_dir, *, debug):
    """Return one database configuration; never connect or log credentials."""
    use_sqlite = _env_value(environ, "USE_SQLITE").lower() in (
        "1", "true", "yes", "on",
    )
    database_url = _env_value(environ, "DATABASE_URL")
    db_keys = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST")
    has_db_fields = any(_env_value(environ, key) for key in db_keys)

    if use_sqlite:
        if not debug:
            raise ImproperlyConfigured(
                "USE_SQLITE requires DEBUG=True. Production must use the existing "
                "persistent PostgreSQL database; do not create a replacement database."
            )
        sqlite_name = _env_value(environ, "SQLITE_NAME") or str(base_dir / "db.sqlite3")
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name,
        }

    if database_url:
        try:
            config = dj_database_url.parse(
                database_url, conn_max_age=60, conn_health_checks=True,
            )
        except (ValueError, KeyError, TypeError):
            # Parser errors can contain the entire URL, including the password.
            raise ImproperlyConfigured(
                "DATABASE_URL is invalid. Check its scheme and encoded credentials."
            ) from None
        if not debug and config["ENGINE"] != "django.db.backends.postgresql":
            raise ImproperlyConfigured(
                "Production DATABASE_URL must identify a persistent PostgreSQL database."
            )
        if not debug and not all(config.get(key) for key in ("NAME", "HOST", "USER")):
            raise ImproperlyConfigured(
                "Production DATABASE_URL must include a database name, host and user."
            )
        return config

    if has_db_fields:
        required = db_keys if not debug else ("DB_NAME",)
        missing = [key for key in required if not _env_value(environ, key)]
        if missing:
            raise ImproperlyConfigured(
                "Incomplete PostgreSQL configuration. Set " + ", ".join(missing)
                + ", or configure DATABASE_URL for the existing database."
            )
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env_value(environ, "DB_NAME"),
            "USER": _env_value(environ, "DB_USER"),
            "PASSWORD": _env_value(environ, "DB_PASSWORD"),
            "HOST": _env_value(environ, "DB_HOST") or "localhost",
            "PORT": _env_value(environ, "DB_PORT") or "5432",
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
        db_sslmode = _env_value(environ, "DB_SSLMODE")
        if db_sslmode:
            config["OPTIONS"] = {"sslmode": db_sslmode}
        return config

    if not debug:
        raise ImproperlyConfigured(
            "No production database configured. Set DATABASE_URL or "
            "DB_NAME, DB_USER, DB_PASSWORD and DB_HOST for the existing persistent "
            "PostgreSQL database. SQLite fallback is only available with DEBUG=True."
        )
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(base_dir / "db.sqlite3"),
    }
