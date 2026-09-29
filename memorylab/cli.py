"""Command line interface for fixtures, policies, runs, and reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .fixtures import load_episodes, write_fixtures
from .policies import POLICY_DESCRIPTIONS, POLICY_NAMES
from .report import build_report
from .runner import run_policy


HONESTY = (
    "Honesty boundary: deterministic rules on synthetic fixtures only. Token overlap is not embeddings. "
    "No trained models, real agent memory, or real retrieval systems. Findings do not generalize to real agents or workloads."
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="memorylab",
        description="Benchmark six deterministic memory policies on synthetic scripted recall tasks.",
        epilog=HONESTY,
    )
    result.add_argument("--version", action="version", version=f"memorylab {__version__}")
    commands = result.add_subparsers(dest="command", required=True)

    fixtures = commands.add_parser(
        "fixtures", help="write the synthetic fictional episode fixtures", epilog=HONESTY
    )
    fixtures.add_argument("--out", required=True, help="directory where episodes.json is written")

    commands.add_parser("policies", help="list policy names and their memory rules", epilog=HONESTY)

    run = commands.add_parser("run", help="run one policy over the synthetic episodes", epilog=HONESTY)
    run.add_argument("--policy", required=True, choices=POLICY_NAMES)
    run.add_argument("--episodes", help="fixture JSON file or directory; defaults to bundled fixtures")
    run.add_argument("--token-budget", type=_nonnegative, default=128, help="memory tokens available per query (default: 128)")
    run.add_argument("--out", help="write canonical JSON to this file instead of stdout")

    report = commands.add_parser("report", help="generate findings for all six policies", epilog=HONESTY)
    report.add_argument("--format", choices=("md", "html"), default="md")
    report.add_argument("--episodes", help="fixture JSON file or directory; defaults to bundled fixtures")
    report.add_argument("--token-budget", type=_nonnegative, default=128, help="memory tokens available per query (default: 128)")
    report.add_argument("--out", help="write report to this file instead of stdout")
    return result


def _nonnegative(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "fixtures":
            path = write_fixtures(args.out)
            print(f"Wrote {path} ({HONESTY})")
            return 0
        if args.command == "policies":
            print("MemoryLab policies (deterministic rules on synthetic fixtures):")
            for name, description in POLICY_DESCRIPTIONS.items():
                print(f"- {name}: {description}")
            print(HONESTY)
            return 0
        fixture_data = load_episodes(args.episodes)
        if args.command == "run":
            output = json.dumps(
                run_policy(fixture_data, args.policy, args.token_budget),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        else:
            output = build_report(fixture_data, args.token_budget, args.format)
        if args.out:
            destination = Path(args.out)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(output, encoding="utf-8", newline="\n")
            print(f"Wrote {destination}")
        else:
            sys.stdout.write(output)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"memorylab: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
