"""SQLite-backed iteration store for cross-session persistence."""

import aiosqlite
from pathlib import Path
from typing import Optional

from effort_agent.evaluators.iteration_tracker import IterationStore


class SQLiteIterationStore(IterationStore):
    """
    SQLite-backed implementation of IterationStore.

    Persists task draft counts and revision notes across sessions.
    Uses aiosqlite for async support.

    Schema:
        iteration_counts(task_key TEXT PRIMARY KEY, count INTEGER, updated_at TEXT)
        revision_notes(task_key TEXT, note TEXT, seq INTEGER)
    """

    def __init__(self, path: str | Path = "effort_iterations.db"):
        """
        Initialize the SQLite store.

        Args:
            path: Path to the SQLite database file.
        """
        self.path = Path(path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = await self._get_conn()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS iteration_counts (
                task_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS revision_notes (
                task_key TEXT NOT NULL,
                note TEXT NOT NULL,
                seq INTEGER NOT NULL,
                PRIMARY KEY (task_key, seq)
            )
        """)
        await conn.commit()

    async def _get_conn(self) -> aiosqlite.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self.path))
            await self._ensure_schema()
        return self._conn

    async def get(self, task_key: str) -> int:
        """Get the draft count for a task key."""
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT count FROM iteration_counts WHERE task_key = ?",
            (task_key,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def set(self, task_key: str, count: int) -> None:
        """Set the draft count for a task key."""
        import datetime

        conn = await self._get_conn()
        await conn.execute(
            """
            INSERT INTO iteration_counts (task_key, count, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(task_key) DO UPDATE SET count = ?, updated_at = ?
            """,
            (task_key, count, count, datetime.datetime.utcnow().isoformat()),
        )
        await conn.commit()

    async def get_revisions(self, task_key: str) -> list[str]:
        """Get revision notes for a task key."""
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT note FROM revision_notes WHERE task_key = ? ORDER BY seq",
            (task_key,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def set_revisions(self, task_key: str, revisions: list[str]) -> None:
        """Set revision notes for a task key (replaces existing)."""
        conn = await self._get_conn()
        await conn.execute(
            "DELETE FROM revision_notes WHERE task_key = ?",
            (task_key,),
        )
        for seq, note in enumerate(revisions):
            await conn.execute(
                "INSERT INTO revision_notes (task_key, note, seq) VALUES (?, ?, ?)",
                (task_key, note, seq),
            )
        await conn.commit()

    async def delete(self, task_key: str) -> None:
        """Delete all data for a task key."""
        conn = await self._get_conn()
        await conn.execute(
            "DELETE FROM iteration_counts WHERE task_key = ?", (task_key,)
        )
        await conn.execute(
            "DELETE FROM revision_notes WHERE task_key = ?", (task_key,)
        )
        await conn.commit()

    async def clear(self) -> None:
        """Clear all data from the store."""
        conn = await self._get_conn()
        await conn.execute("DELETE FROM iteration_counts")
        await conn.execute("DELETE FROM revision_notes")
        await conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def stats(self) -> dict:
        """
        Get statistics about the store.

        Returns:
            A dict with total_tasks, total_drafts, etc.
        """
        conn = await self._get_conn()

        cursor = await conn.execute("SELECT COUNT(*), SUM(count) FROM iteration_counts")
        row = await cursor.fetchone()
        total_tasks = row[0] if row[0] else 0
        total_drafts = row[1] if row[1] else 0

        avg = total_drafts / total_tasks if total_tasks > 0 else 0.0

        return {
            "total_tasks": total_tasks,
            "total_drafts": total_drafts,
            "average_drafts_per_task": avg,
        }
