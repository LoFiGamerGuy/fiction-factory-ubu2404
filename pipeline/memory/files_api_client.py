"""FilesAPIClient — uploads series assets to Claude Files API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FILE_IDS_FILENAME = "file_ids.json"


class FilesAPIClient:
    """Uploads series bible, voice profiles, and character sheets to the Claude Files API.

    File IDs are persisted in ``data/{series_id}/file_ids.json`` so they can be
    reused across pipeline runs without re-uploading.

    Degrades gracefully: if the Files API is unavailable or fails, methods return
    empty strings / empty dicts and log a warning rather than raising.
    """

    def __init__(self) -> None:
        import anthropic  # noqa: PLC0415

        self._client = anthropic.Anthropic()

    # ── Public API ─────────────────────────────────────────────────────────────

    def upload_series_bible(self, bible_path: Path, series_id: str) -> str:
        """Upload the series bible file; return file_id (or "" on failure)."""
        file_id = self._upload_file(bible_path)
        if file_id:
            ids = self._load_file_ids(series_id)
            ids["series_bible"] = file_id
            self._save_file_ids(series_id, ids)
        return file_id

    def upload_voice_profile(self, profile_path: Path, series_id: str) -> str:
        """Upload the voice profile file; return file_id (or "" on failure)."""
        file_id = self._upload_file(profile_path)
        if file_id:
            ids = self._load_file_ids(series_id)
            ids["voice_profile"] = file_id
            self._save_file_ids(series_id, ids)
        return file_id

    def upload_character_sheets(self, char_dir: Path, series_id: str) -> dict[str, str]:
        """Upload each .md or .yaml file in char_dir; return {stem: file_id}."""
        uploaded: dict[str, str] = {}
        if not char_dir.is_dir():
            logger.warning("upload_character_sheets: %s is not a directory", char_dir)
            return uploaded

        for char_file in char_dir.iterdir():
            if char_file.suffix not in {".md", ".yaml", ".yml"}:
                continue
            file_id = self._upload_file(char_file)
            if file_id:
                uploaded[char_file.stem] = file_id

        if uploaded:
            ids = self._load_file_ids(series_id)
            ids.update({f"char_{stem}": fid for stem, fid in uploaded.items()})
            self._save_file_ids(series_id, ids)

        return uploaded

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _upload_file(self, path: Path) -> str:
        """Upload a single file to the Files API; return file_id or "" on error."""
        try:
            content = path.read_bytes()
            response = self._client.beta.files.upload(
                file=(path.name, content, "text/plain"),
            )
            return str(response.id)
        except AttributeError as exc:
            logger.warning(
                "FilesAPIClient: Files API unavailable (%s) — skipping upload of %s.",
                exc,
                path.name,
            )
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "FilesAPIClient: upload of %s failed: %s",
                path.name,
                exc,
            )
            return ""

    def _load_file_ids(self, series_id: str) -> dict[str, str]:
        """Read data/{series_id}/file_ids.json; return {} if not found."""
        ids_path = Path("data") / series_id / _FILE_IDS_FILENAME
        if not ids_path.exists():
            return {}
        try:
            raw: dict[str, str] = json.loads(ids_path.read_text(encoding="utf-8"))
            return raw
        except Exception as exc:  # noqa: BLE001
            logger.warning("FilesAPIClient._load_file_ids failed: %s", exc)
            return {}

    def _save_file_ids(self, series_id: str, file_ids: dict[str, str]) -> None:
        """Write merged file_ids dict to data/{series_id}/file_ids.json."""
        ids_path = Path("data") / series_id / _FILE_IDS_FILENAME
        try:
            ids_path.parent.mkdir(parents=True, exist_ok=True)
            ids_path.write_text(json.dumps(file_ids, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("FilesAPIClient._save_file_ids failed: %s", exc)
