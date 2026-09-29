from __future__ import annotations

import json

from memorylab.fixtures import SYNTHETIC_LABEL, default_episodes, fixture_json, load_episodes, write_fixtures


def test_fixture_generation_is_byte_identical(tmp_path):
    first = write_fixtures(tmp_path / "first").read_bytes()
    second = write_fixtures(tmp_path / "second").read_bytes()
    assert first == second
    assert first.endswith(b"\n")


def test_fixtures_are_labelled_synthetic_and_include_required_scenarios():
    data = default_episodes()
    assert data["label"] == SYNTHETIC_LABEL
    assert data["seed"] == 0
    assert {episode["id"] for episode in data["episodes"]} >= {
        "control_basics",
        "correction_and_expiry",
        "corruption_trap",
        "distractors",
    }
    assert any(episode["control"] for episode in data["episodes"])


def test_fixture_file_loads_from_directory(tmp_path):
    written = write_fixtures(tmp_path)
    loaded = load_episodes(tmp_path)
    assert loaded == json.loads(written.read_text(encoding="utf-8"))
    assert fixture_json().encode("utf-8") == written.read_bytes()
