"""Tests for Claude Files API metadata persistence."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from pipeline.memory.files_api_client import FilesAPIClient


class _FakeFilesAPI:
    def __init__(self) -> None:
        self.uploaded_names: list[str] = []

    def upload(self, file: tuple[str, bytes, str]) -> SimpleNamespace:
        self.uploaded_names.append(file[0])
        return SimpleNamespace(id=f"file-{len(self.uploaded_names)}")


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.files = _FakeFilesAPI()
        self.beta = SimpleNamespace(files=self.files)


def test_files_api_client_persists_ids_under_run_local_data_root(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    characters = assets / "characters"
    characters.mkdir(parents=True)
    bible = assets / "bible.md"
    voice = assets / "voice.yaml"
    emma = characters / "emma.md"
    ignored = characters / "notes.txt"
    bible.write_text("Series bible", encoding="utf-8")
    voice.write_text("profile_id: voice", encoding="utf-8")
    emma.write_text("# Emma", encoding="utf-8")
    ignored.write_text("not uploaded", encoding="utf-8")

    fake_client = _FakeAnthropicClient()
    data_root = tmp_path / "run-data"
    client = FilesAPIClient(data_root=data_root, client=fake_client)

    uploaded = client.upload_series_assets(
        series_id="series-1",
        series_bible_path=bible,
        voice_profile_path=voice,
        character_sheets_dir=characters,
    )

    assert uploaded == {
        "series_bible": "file-1",
        "voice_profile": "file-2",
        "char_emma": "file-3",
    }
    assert fake_client.files.uploaded_names == ["bible.md", "voice.yaml", "emma.md"]
    saved_path = data_root / "series-1" / "file_ids.json"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == uploaded
    assert client.load_file_ids("series-1") == uploaded


def test_files_api_client_gracefully_skips_unavailable_client(tmp_path: Path) -> None:
    bible = tmp_path / "bible.md"
    bible.write_text("Series bible", encoding="utf-8")
    broken_client = SimpleNamespace(beta=SimpleNamespace(files=SimpleNamespace()))
    client = FilesAPIClient(data_root=tmp_path / "run-data", client=broken_client)

    uploaded = client.upload_series_assets(series_id="series-1", series_bible_path=bible)

    assert uploaded == {}
    assert client.load_file_ids("series-1") == {}
