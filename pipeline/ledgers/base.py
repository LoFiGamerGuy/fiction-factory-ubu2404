"""Append-only SQLite ledger base class.

Every concrete ledger stores events in a single-table SQLite database.
Only INSERT is allowed — no UPDATE or DELETE. The event_id PRIMARY KEY
provides idempotency: re-appending the same event raises LedgerError.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class LedgerError(Exception):
    """Raised for ledger contract violations (duplicate event, bad payload, etc.)."""


class BaseLedger:
    """SQLite-backed append-only event log.

    Subclasses call ``_append(event_id, payload)`` and ``_all_payloads()``.
    They must never issue UPDATE or DELETE SQL.
    """

    TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS events (
            event_id   TEXT NOT NULL PRIMARY KEY,
            payload    TEXT NOT NULL,
            appended_at TEXT NOT NULL
        )
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(self.TABLE_DDL)
        self._conn.commit()

    def _append(self, event_id: str, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        try:
            self._conn.execute(
                "INSERT INTO events (event_id, payload, appended_at) VALUES (?, ?, ?)",
                (event_id, json.dumps(payload), now),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise LedgerError(f"Duplicate event_id '{event_id}' — ledger is append-only.") from exc

    def _all_payloads(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT payload FROM events ORDER BY rowid ASC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def _payloads_where(self, column: str, value: str) -> list[dict[str, Any]]:
        """Return payloads where payload JSON field matches value (simple equality)."""
        rows = self._conn.execute("SELECT payload FROM events ORDER BY rowid ASC").fetchall()
        result = []
        for (raw,) in rows:
            p = json.loads(raw)
            if p.get(column) == value:
                result.append(p)
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> BaseLedger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
