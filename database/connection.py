"""
Invoice Generator Database Connection Manager
Provides async SQLite connection with WAL mode for concurrent access.
"""

import aiosqlite
from pathlib import Path
from loguru import logger

from backend.config import settings
from database.models import ALL_TABLES


class DatabaseManager:
    """Manages SQLite database connections and initialization."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self._ensure_directory()

    def _ensure_directory(self):
        """Ensure the database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def get_connection(self) -> aiosqlite.Connection:
        """Get a new database connection with WAL mode enabled."""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        return db

    async def initialize(self):
        """Create all tables if they don't exist."""
        logger.info("Initializing database tables...")
        db = await self.get_connection()
        try:
            for table_sql in ALL_TABLES:
                await db.execute(table_sql)
            await db.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
        finally:
            await db.close()

    async def execute(self, query: str, params: tuple = None):
        """Execute a single query."""
        db = await self.get_connection()
        try:
            if params:
                cursor = await db.execute(query, params)
            else:
                cursor = await db.execute(query)
            await db.commit()
            return cursor
        finally:
            await db.close()

    async def execute_returning_id(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT and return the last row id."""
        db = await self.get_connection()
        try:
            if params:
                cursor = await db.execute(query, params)
            else:
                cursor = await db.execute(query)
            await db.commit()
            return cursor.lastrowid
        finally:
            await db.close()

    async def fetch_one(self, query: str, params: tuple = None) -> dict | None:
        """Fetch a single row as a dictionary."""
        db = await self.get_connection()
        try:
            if params:
                cursor = await db.execute(query, params)
            else:
                cursor = await db.execute(query)
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            await db.close()

    async def fetch_all(self, query: str, params: tuple = None) -> list[dict]:
        """Fetch all rows as list of dictionaries."""
        db = await self.get_connection()
        try:
            if params:
                cursor = await db.execute(query, params)
            else:
                cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await db.close()


# Global database manager instance
db_manager = DatabaseManager()
