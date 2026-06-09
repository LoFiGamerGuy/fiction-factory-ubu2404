"""Phase 11 orchestration hooks: Paperclip, WUPHF, and ROMA integration."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from pipeline.book_structure_planner import BookStructurePlanner
from pipeline.orchestrator import main


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "pipeline_config.json"
    config_path.write_text(
        json.dumps(
            {
                "series_root": str(tmp_path / "series"),
                "series_id": "series_test",
                "book_id": "book01",
                "output_dir": str(tmp_path / "output"),
                "approval_timeout_s": 5,
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_specs(tmp_path: Path) -> Path:
    series_dir = tmp_path / "series" / "series_test"
    book_dir = series_dir / "data" / "books" / "book01"
    book_dir.mkdir(parents=True, exist_ok=True)
    series_spec = {
        "series_id": "series_test",
        "genre_config": {
            "genre_name": "romance",
            "heat_curve": "flat",
            "word_count_target": 12,
            "chapter_count": 1,
            "scene_function_vocabulary": ["resolution"],
            "required_scene_slots": ["HEA_or_HFN"],
            "hea_required": True,
        },
    }
    book_spec = {"chapter_count": 1, "scenes_per_chapter": 1, "word_count_target": 12}
    series_spec_path = series_dir / "spec.yaml"
    series_spec_path.write_text(yaml.dump(series_spec), encoding="utf-8")
    (book_dir / "spec.yaml").write_text(yaml.dump(book_spec), encoding="utf-8")
    return series_spec_path


def _write_publishable_book(tmp_path: Path) -> None:
    _write_specs(tmp_path)
    series_dir = tmp_path / "series" / "series_test"
    book_dir = series_dir / "data" / "books" / "book01"
    series_spec = yaml.safe_load((series_dir / "spec.yaml").read_text(encoding="utf-8"))
    book_spec = yaml.safe_load((book_dir / "spec.yaml").read_text(encoding="utf-8"))
    BookStructurePlanner().plan(
        book_id="book01",
        series_id="series_test",
        series_spec=series_spec,
        book_spec=book_spec,
        book_dir=book_dir,
        inventory_path=book_dir / "scene_inventory.json",
    )
    (book_dir / "scene_history.jsonl").write_text(
        json.dumps(
            {
                "scene_id": "ch01_sc01",
                "chapter": 1,
                "act": 3,
                "heat_level": 3,
                "scene_function": "resolution",
                "required_slot_id": "HEA_or_HFN",
                "word_count": 12,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (book_dir / "manuscript.md").write_text(
        "one two three four five six seven eight nine ten eleven twelve",
        encoding="utf-8",
    )


def test_init_book_runs_phase11_control_flow(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)
    _write_specs(tmp_path)
    events: list[tuple[Any, ...]] = []

    class FakePaperclip:
        def check_budget(self, agent_role: str) -> bool:
            events.append(("budget", agent_role))
            return True

        def request_approval(
            self, gate_name: str, context: dict[str, Any], timeout_s: int = 3600
        ) -> bool:
            events.append(("approval", gate_name, context, timeout_s))
            return True

        def record_cost(self, agent_role: str, cost_usd: float, tokens_used: int = 0) -> None:
            events.append(("cost", agent_role, cost_usd, tokens_used))

    class FakeWUPHF:
        def post_to_channel(
            self,
            channel: str,
            message: str,
            room: str | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            events.append(("channel", channel, message, room, metadata))

        def update_wiki(self, page: str, content: str, author: str = "pipeline") -> None:
            events.append(("wiki", page, content, author))

    class FakeROMA:
        def decompose(self, series_spec: dict[str, Any]) -> SimpleNamespace:
            events.append(("roma_decompose", series_spec))
            return SimpleNamespace(book_plans=[SimpleNamespace(total_scenes=1)])

        def verify(self, plan: SimpleNamespace) -> SimpleNamespace:
            events.append(("roma_verify", plan))
            return SimpleNamespace(valid=True, errors=[])

    monkeypatch.setattr("pipeline.control.paperclip_client.PaperclipClient", FakePaperclip)
    monkeypatch.setattr("pipeline.control.wuphf_client.WUPHFClient", FakeWUPHF)
    monkeypatch.setattr("pipeline.control.roma_client.ROMAClient", FakeROMA)

    assert main(["--init-book", "series_test", "1", "--config", str(config_path)]) == 0

    assert ("budget", "orchestrator") in events
    assert any(event[0] == "approval" and event[1] == "spec_signoff" for event in events)
    assert any(event[0] == "roma_decompose" for event in events)
    assert any(event[0] == "roma_verify" for event in events)
    assert any(event[0] == "cost" for event in events)
    assert any(event[0] == "channel" and event[1] == "pipeline" for event in events)
    assert any(event[0] == "wiki" and event[1] == "planning/series_test/book01" for event in events)


def test_validate_spec_can_read_wuphf_wiki_page(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)
    series_spec_path = _write_specs(tmp_path)
    spec_text = series_spec_path.read_text(encoding="utf-8")

    class FakeWUPHF:
        def read_wiki(self, page: str) -> str:
            assert page == "series-specs/series_test"
            return spec_text

    monkeypatch.setattr("pipeline.control.wuphf_client.WUPHFClient", FakeWUPHF)

    assert (
        main(["--validate-spec", "wiki:series-specs/series_test", "--config", str(config_path)])
        == 0
    )


def test_job_halts_when_paperclip_budget_exhausted(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)

    class FakePaperclip:
        def check_budget(self, agent_role: str) -> bool:
            return False

    monkeypatch.setattr("pipeline.control.paperclip_client.PaperclipClient", FakePaperclip)

    assert main(["--job", "ch01_sc01", "--config", str(config_path)]) == 1


def test_init_book_fails_when_roma_verification_fails(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)
    _write_specs(tmp_path)

    class FakePaperclip:
        def check_budget(self, agent_role: str) -> bool:
            return True

        def request_approval(
            self, gate_name: str, context: dict[str, Any], timeout_s: int = 3600
        ) -> bool:
            return True

    class FakeROMA:
        def decompose(self, series_spec: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(book_plans=[])

        def verify(self, plan: SimpleNamespace) -> SimpleNamespace:
            return SimpleNamespace(valid=False, errors=["invalid act plan"])

    monkeypatch.setattr("pipeline.control.paperclip_client.PaperclipClient", FakePaperclip)
    monkeypatch.setattr("pipeline.control.roma_client.ROMAClient", FakeROMA)

    assert main(["--init-book", "series_test", "1", "--config", str(config_path)]) == 1


def test_book_publish_requires_manuscript_signoff(tmp_path: Path, monkeypatch: Any) -> None:
    config_path = _write_config(tmp_path)
    _write_publishable_book(tmp_path)

    class FakePaperclip:
        def check_budget(self, agent_role: str) -> bool:
            return True

        def request_approval(
            self, gate_name: str, context: dict[str, Any], timeout_s: int = 3600
        ) -> bool:
            return gate_name != "manuscript_signoff"

    monkeypatch.setattr("pipeline.control.paperclip_client.PaperclipClient", FakePaperclip)

    assert main(["--book-publish", "book01", "--config", str(config_path)]) == 1
    assert not (tmp_path / "output" / "book01" / "generation_report.json").exists()
