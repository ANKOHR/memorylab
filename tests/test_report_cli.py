from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from memorylab.fixtures import default_episodes
from memorylab.report import build_report


ROOT = Path(__file__).resolve().parents[1]


def call_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "memorylab", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_markdown_report_has_protocol_results_findings_limits_and_honesty():
    report = build_report(default_episodes(), token_budget=128)
    assert "## Protocol" in report
    assert "## Results" in report and "| Policy | Task success |" in report
    assert "## Findings" in report
    assert "## Limits" in report
    assert "## Honesty statement" in report
    assert "not embeddings" in report
    assert "No trained models" in report


def test_markdown_and_html_reports_are_byte_deterministic():
    first = build_report(default_episodes(), 128, "md")
    assert first == build_report(default_episodes(), 128, "md")
    html_first = build_report(default_episodes(), 128, "html")
    assert html_first == build_report(default_episodes(), 128, "html")
    assert "<table>" in html_first and "</html>" in html_first
    assert "Limits" in html_first and "embeddings" in html_first


def test_cli_fixtures_subcommand_writes_json_and_states_honesty(tmp_path):
    result = call_cli("fixtures", "--out", tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "episodes.json").exists()
    assert "synthetic" in result.stdout.casefold()
    assert json.loads((tmp_path / "episodes.json").read_text(encoding="utf-8"))["seed"] == 0


def test_cli_policies_subcommand_lists_six_policies_and_honesty():
    result = call_cli("policies")
    assert result.returncode == 0, result.stderr
    assert all(name in result.stdout for name in ("full_context", "summary", "token_overlap", "episodic", "structured", "hybrid"))
    assert "no trained models" in result.stdout.casefold()
    help_result = call_cli("--help")
    assert "not embeddings" in help_result.stdout
    run_help = call_cli("run", "--help")
    assert "not embeddings" in run_help.stdout


def test_cli_run_subcommand_emits_deterministic_json(tmp_path):
    output = tmp_path / "run.json"
    result = call_cli("run", "--policy", "structured", "--out", output)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["policy"] == "structured"
    assert data["metrics"]["query_count"] == 7
    assert "memory" in data["episode_results"][0]


def test_cli_report_subcommand_writes_markdown_and_html(tmp_path):
    markdown = tmp_path / "report.md"
    first = call_cli("report", "--format", "md", "--out", markdown)
    assert first.returncode == 0, first.stderr
    assert "## Protocol" in markdown.read_text(encoding="utf-8")
    html_path = tmp_path / "report.html"
    second = call_cli("report", "--format", "html", "--out", html_path)
    assert second.returncode == 0, second.stderr
    assert "<table>" in html_path.read_text(encoding="utf-8")


def test_cli_run_to_stdout_and_report_to_stdout_smoke():
    run = call_cli("run", "--policy", "full_context")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["policy"] == "full_context"
    report = call_cli("report", "--format", "md")
    assert report.returncode == 0, report.stderr
    assert "## Limits" in report.stdout
