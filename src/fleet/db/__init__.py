"""Postgres-backed controller registry (needs the ``[fleet]`` extra).

Imported only when ``DATABASE_URL`` is set, so the base install never loads
SQLAlchemy or asyncpg.
"""
