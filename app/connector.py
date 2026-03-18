"""
Connector Layer: SQLAlchemy-based read-only access to legacy databases.

Supports ODBC drivers required for AS/400 (IBM i) and legacy SQL Server.
All sessions are strictly read-only; write operations are not permitted.
"""

from contextlib import contextmanager
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class LegacyConnector:
    """
    Read-only connector for legacy databases via SQLAlchemy.

    Connection strings should use ODBC for AS/400 (e.g. IBM i Access ODBC)
    or SQL Server ODBC drivers. Example:
      - AS/400: "mssql+pyodbc://user:pass@host/db?driver=IBM+i+Access+ODBC+Driver"
      - SQL Server: "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server"
    """

    def __init__(
        self,
        connection_string: str,
        *,
        pool_pre_ping: bool = True,
        echo: bool = False,
    ) -> None:
        """
        Initialize the connector with a SQLAlchemy-compatible connection string.

        :param connection_string: Database URL (e.g. sqlite, mssql+pyodbc, ...).
        :param pool_pre_ping: If True, connections are checked for liveness before use.
        :param echo: If True, SQLAlchemy will log SQL statements.
        """
        self._connection_string = connection_string
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._pool_pre_ping = pool_pre_ping
        self._echo = echo

    def _get_engine(self) -> Engine:
        """Create or return the cached SQLAlchemy engine."""
        if self._engine is None:
            # READ COMMITTED not supported by SQLite; use only for ODBC backends
            opts: dict[str, str] = {}
            if "sqlite" not in self._connection_string.split("://")[0].lower():
                opts["isolation_level"] = "READ COMMITTED"
            self._engine = create_engine(
                self._connection_string,
                pool_pre_ping=self._pool_pre_ping,
                echo=self._echo,
                execution_options=opts if opts else {},
            )
        return self._engine

    def _get_session_factory(self) -> sessionmaker:
        """Create or return the session factory with read-only behavior."""
        if self._session_factory is None:
            engine = self._get_engine()
            self._session_factory = sessionmaker(
                bind=engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._session_factory

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a strictly read-only session context.

        The session is configured to avoid writes; for databases that support
        it, a read-only transaction hint may be applied.
        """
        factory = self._get_session_factory()
        session = factory()
        try:
            # Enforce read-only: attempt to set transaction read-only where supported
            try:
                if session.get_bind().dialect.name == "sqlite":
                    session.execute(text("PRAGMA query_only = ON"))
                # Some backends support transaction-level read-only, but SQL syntax
                # is not portable; we rely primarily on strict SELECT-only execution
                # in execute_read() plus DB permissions in production.
            except Exception:
                # Not all backends support this; continue with session discipline
                pass
            yield session
            # Explicitly avoid committing to ensure no accidental writes are persisted.
            # Rollback also ends the transaction cleanly across backends.
            session.rollback()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _assert_read_only_sql(self, sql: str) -> None:
        """
        Enforce read-only SQL at runtime.

        This is a defensive control to prevent accidental DML/DDL even if a caller
        passes arbitrary SQL. In production, also use DB-side permissions/roles.
        """
        s = (sql or "").lstrip().lower()
        if not s:
            raise ValueError("Empty SQL is not allowed")
        # Allow common read-only entry points
        allowed_prefixes = ("select", "with", "pragma", "show", "describe", "explain")
        if not s.startswith(allowed_prefixes):
            raise PermissionError("Only read-only statements are allowed")

    def execute_read(
        self,
        sql: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a read-only SQL statement and return rows as list of dicts.

        :param sql: Read-only statement (SELECT/CTE/PRAGMA/EXPLAIN...). Non read-only
                    statements are rejected.
        :param parameters: Optional bound parameters for the query.
        :return: List of row dicts (column name -> value).
        """
        self._assert_read_only_sql(sql)
        parameters = parameters or {}
        with self.session() as s:
            result = s.execute(text(sql), parameters)
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def close(self) -> None:
        """Release engine and connection pool."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
        self._session_factory = None
