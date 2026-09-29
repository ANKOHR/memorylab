"""Deterministic Markdown and HTML findings reports."""

from __future__ import annotations

import html
from typing import Any

from .metrics import metric_definitions
from .runner import run_all


HONESTY = (
    "MemoryLab uses deterministic rules on synthetic episodes. Token-overlap similarity is not embeddings. "
    "No trained models, real agent memory, or real retrieval systems are involved. Findings apply to these fixtures only."
)


def build_report(fixture_data: dict[str, Any], token_budget: int = 128, output_format: str = "md") -> str:
    runs = run_all(fixture_data, token_budget)
    markdown = _markdown_report(fixture_data, runs, token_budget)
    if output_format == "md":
        return markdown
    if output_format == "html":
        return _html_report(markdown)
    raise ValueError("Report format must be 'md' or 'html'")


def _markdown_report(fixture_data: dict[str, Any], runs: list[dict[str, Any]], token_budget: int) -> str:
    report: list[str] = [
        "# MemoryLab findings",
        "",
        f"> {HONESTY}",
        "",
        "## Protocol",
        "",
        f"- Fixture label: {fixture_data['label']}",
        f"- Fixture seed: {fixture_data['seed']}; no random number generator is used.",
        f"- Episodes: {len(fixture_data['episodes'])}; policies: {len(runs)}.",
        f"- Memory token budget: {token_budget} whitespace-separated tokens per query. Query text is counted in total token use but is outside that memory budget.",
        "- Events are processed in listed order. `set` changes an absent key, `correct` replaces its value, and `expire` removes it.",
        "- Token-overlap ranking counts shared distinct lowercase alphanumeric tokens. Ties prefer the later event, then the lexically smaller fact ID.",
        "",
        "## Results",
        "",
        "| Policy | Task success | Retrieval accuracy | Memory tokens used / budget | Total tokens used | Corruptions |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        metric = run["metrics"]
        retrieval = _percent(metric["retrieval_accuracy"])
        report.append(
            f"| {run['policy']} | {_percent(metric['task_success_rate'])} "
            f"({metric['task_successes']}/{metric['query_count']}) | {retrieval} "
            f"({metric['retrieval_hits']}/{metric['answerable_queries']}) | "
            f"{metric['memory_tokens_used']} / {metric['memory_token_budget_total']} | "
            f"{metric['tokens_used']} | {metric['corruption_count']} |"
        )

    report.extend(["", "## Findings", ""])
    best_rate = max(run["metrics"]["task_success_rate"] for run in runs)
    best_policies = [run["policy"] for run in runs if run["metrics"]["task_success_rate"] == best_rate]
    least_memory = min(run["metrics"]["memory_tokens_used"] for run in runs)
    lean_policies = [run["policy"] for run in runs if run["metrics"]["memory_tokens_used"] == least_memory]
    summary_run = next(run for run in runs if run["policy"] == "summary")
    trap_episode = next(
        (episode for episode in summary_run["episode_results"] if episode["episode_id"] == "corruption_trap"),
        None,
    )
    report.extend(
        [
            f"- Highest task success on this fixture set: {', '.join(best_policies)} at {_percent(best_rate)}.",
            f"- Lowest memory-token total: {', '.join(lean_policies)} at {least_memory} tokens.",
            _trap_finding(trap_episode, summary_run),
            "- These observations describe only the listed synthetic episodes and configured budget.",
            "",
            "## Metric definitions",
            "",
        ]
    )
    for name, description in metric_definitions().items():
        report.append(f"- **{name}:** {description}")

    report.extend(
        [
            "",
            "## Limits",
            "",
            "The fixture set is small, scripted, synthetic, and designed for hand checking. It does not sample real users, real agents, production memory stores, or real retrieval workloads. The policies are simplified deterministic rules, not trained models. Token overlap is literal token matching, not embeddings. The results do not establish which architecture is best in general and do not generalize to real agents or real workloads.",
            "",
            "## Honesty statement",
            "",
            HONESTY,
            "",
        ]
    )
    return "\n".join(report)


def _trap_finding(trap_episode: dict[str, Any] | None, summary_run: dict[str, Any]) -> str:
    if trap_episode is not None and trap_episode["queries"]:
        row = trap_episode["queries"][0]
        return (
            f"- The summary policy answered Mira's assigned-to query with {row['answer']!r}; "
            f"the planted answer is {row['expected_answer']!r}. This fixture records "
            f"{trap_episode['metrics']['corruption_count']} corruption for that policy."
        )
    return f"- The summary policy recorded {summary_run['metrics']['corruption_count']} corruptions across these fixtures."


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _html_report(markdown: str) -> str:
    lines = markdown.splitlines()
    output = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>MemoryLab findings</title>",
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1080px;margin:2rem auto;padding:0 1rem;color:#20242a}table{border-collapse:collapse}th,td{border:1px solid #c8cdd4;padding:.45rem .7rem;text-align:left}blockquote{border-left:4px solid #5788c7;padding-left:1rem;color:#334}</style>",
        "</head>",
        "<body>",
    ]
    in_table = False
    table_header_written = False
    in_list = False
    for line in lines:
        if line.startswith("| "):
            if not in_table:
                output.append("<table>")
                in_table = True
                table_header_written = False
            if line.startswith("| ---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            tag = "th" if not table_header_written else "td"
            output.append("<tr>" + "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in cells) + "</tr>")
            table_header_written = True
            continue
        if in_table:
            output.append("</table>")
            in_table = False
            table_header_written = False
        if line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            output.append("</ul>")
            in_list = False
        if line.startswith("# "):
            output.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            output.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("> "):
            output.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif line:
            output.append(f"<p>{_inline(line)}</p>")
    if in_table:
        output.append("</table>")
    if in_list:
        output.append("</ul>")
    output.extend(["</body>", "</html>", ""])
    return "\n".join(output)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    import re

    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
