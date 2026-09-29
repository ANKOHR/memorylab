"""Deterministic synthetic episodes used by the MemoryLab benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SYNTHETIC_LABEL = "Synthetic fictional benchmark data. No real people or agents."
SEED = 0


def default_episodes() -> dict[str, Any]:
    """Return the complete fixture set as plain JSON-compatible data."""
    return {
        "schema_version": 1,
        "label": SYNTHETIC_LABEL,
        "seed": SEED,
        "episodes": [
            {
                "id": "control_basics",
                "control": True,
                "description": "Two direct lookups that a perfect memory can answer.",
                "events": [
                    _fact("f001", "t01", "set", "Ada", "favorite color", "indigo"),
                    _fact("f002", "t02", "set", "Bo", "favorite color", "ochre"),
                    _query("q001", "t03", "Ada favorite color?", "Ada", "favorite color", "f001"),
                    _query("q002", "t04", "Bo favorite color?", "Bo", "favorite color", "f002"),
                ],
            },
            {
                "id": "correction_and_expiry",
                "control": False,
                "description": "A corrected value is recalled, then an expired value is absent.",
                "events": [
                    _fact("f101", "t01", "set", "Lin", "access code", "silver"),
                    _fact("f102", "t02", "correct", "Lin", "access code", "gold"),
                    _query("q101", "t03", "Lin access code?", "Lin", "access code", "f102"),
                    _fact("f103", "t04", "expire", "Lin", "access code", None),
                    _query("q102", "t05", "Lin access code now?", "Lin", "access code", None),
                ],
            },
            {
                "id": "corruption_trap",
                "control": False,
                "description": "A relation-only summary can attach Noah's value to Mira.",
                "events": [
                    _fact("f201", "t01", "set", "Mira", "assigned to", "North"),
                    _fact("f202", "t02", "set", "Noah", "assigned to", "South"),
                    _query("q201", "t03", "Mira assigned to?", "Mira", "assigned to", "f201"),
                ],
            },
            {
                "id": "distractors",
                "control": False,
                "description": "Repeated words and nearby facts exercise deterministic retrieval ranking.",
                "events": [
                    _fact("f301", "t01", "set", "Ivo", "badge", "amber"),
                    _fact("f302", "t02", "set", "Uma", "badge", "violet"),
                    _fact("f303", "t03", "set", "Kian", "badge", "amber"),
                    _fact("f304", "t04", "set", "Ivo", "favorite color", "teal"),
                    _query("q301", "t05", "Ivo badge?", "Ivo", "badge", "f301"),
                    _query("q302", "t06", "Kian badge?", "Kian", "badge", "f303"),
                ],
            },
        ],
    }


def _fact(
    fact_id: str,
    at: str,
    op: str,
    subject: str,
    relation: str,
    object_value: str | None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "fact",
        "fact_id": fact_id,
        "at": at,
        "op": op,
        "subject": subject,
        "relation": relation,
    }
    if object_value is not None:
        item["object"] = object_value
    return item


def _query(
    query_id: str,
    at: str,
    text: str,
    subject: str,
    relation: str,
    target_fact_id: str | None,
) -> dict[str, Any]:
    return {
        "type": "query",
        "query_id": query_id,
        "at": at,
        "text": text,
        "subject": subject,
        "relation": relation,
        "target_fact_id": target_fact_id,
    }


def fixture_json() -> str:
    """Serialize fixtures canonically, with one trailing newline."""
    return json.dumps(default_episodes(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_fixtures(out_dir: str | Path) -> Path:
    """Write the canonical episode fixture file and return its path."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "episodes.json"
    destination.write_text(fixture_json(), encoding="utf-8", newline="\n")
    return destination


def load_episodes(path: str | Path | None = None) -> dict[str, Any]:
    """Load supplied fixture JSON, or return the bundled deterministic set."""
    if path is None:
        return default_episodes()
    source = Path(path)
    if source.is_dir():
        source = source / "episodes.json"
    return json.loads(source.read_text(encoding="utf-8"))
