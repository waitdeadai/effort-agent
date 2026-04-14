"""JSONL file-backed iteration store for cross-session persistence."""

import json
from pathlib import Path
from typing import Optional

from effort_agent.evaluators.iteration_tracker import IterationStore


class FileIterationStore(IterationStore):
    """
    Simple JSON file-backed implementation of IterationStore.

    Persists task draft counts and revision notes to a single JSON file.
    Simpler than SQLite but suitable for single-user/local use.

    Schema (JSON):
    {
        "counts": {"task_key": count, ...},
        "revisions": {"task_key": ["note1", "note2", ...], ...}
    }
    """

    def __init__(self, path: str | Path = "effort_iterations.json"):
        """
        Initialize the file store.

        Args:
            path: Path to the JSON file.
        """
        self.path = Path(path)
        self._data: Optional[dict] = None

    def _load(self) -> dict:
        """Load data from file or return empty structure."""
        if self._data is not None:
            return self._data

        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {"counts": {}, "revisions": {}}
        else:
            self._data = {"counts": {}, "revisions": {}}

        return self._data

    def _save(self) -> None:
        """Save data to file."""
        if self._data is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")

    def get(self, task_key: str) -> int:
        """Get the draft count for a task key."""
        data = self._load()
        return data.get("counts", {}).get(task_key, 0)

    def set(self, task_key: str, count: int) -> None:
        """Set the draft count for a task key."""
        data = self._load()
        data.setdefault("counts", {})[task_key] = count
        self._save()

    def get_revisions(self, task_key: str) -> list[str]:
        """Get revision notes for a task key."""
        data = self._load()
        return list(data.get("revisions", {}).get(task_key, []))

    def set_revisions(self, task_key: str, revisions: list[str]) -> None:
        """Set revision notes for a task key (replaces existing)."""
        data = self._load()
        data.setdefault("revisions", {})[task_key] = revisions
        self._save()

    def delete(self, task_key: str) -> None:
        """Delete all data for a task key."""
        data = self._load()
        data.get("counts", {}).pop(task_key, None)
        data.get("revisions", {}).pop(task_key, None)
        self._save()

    def clear(self) -> None:
        """Clear all data from the store."""
        self._data = {"counts": {}, "revisions": {}}
        self._save()

    def stats(self) -> dict:
        """Get statistics about the store."""
        data = self._load()
        counts = data.get("counts", {})
        total_tasks = len(counts)
        total_drafts = sum(counts.values())
        avg = total_drafts / total_tasks if total_tasks > 0 else 0.0

        return {
            "total_tasks": total_tasks,
            "total_drafts": total_drafts,
            "average_drafts_per_task": avg,
        }
