"""Conexão com Postgres."""
from __future__ import annotations

import psycopg

from .config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url)
