"""Event runner that applies memory policies and records auditable metrics."""

from __future__ import annotations

from typing import Any

from .metrics import summarize_queries
from .policies import POLICY_NAMES, create_policy, resolve_events


def run_policy(
    fixture_data: dict[str, Any],
    policy_name: str,
    token_budget: int = 128,
) -> dict[str, Any]:
    if token_budget < 0:
        raise ValueError("Token budget must be zero or greater")
    if policy_name not in POLICY_NAMES:
        raise ValueError(f"Unknown policy {policy_name!r}. Choose from: {', '.join(POLICY_NAMES)}")

    episode_results: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for episode in fixture_data["episodes"]:
        policy = create_policy(policy_name)
        facts: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        for event in episode["events"]:
            if event["type"] == "fact":
                ordered = {**event, "_order": len(facts)}
                facts.append(ordered)
                policy.observe(event)
                continue

            if event["type"] != "query":
                raise ValueError(f"Unknown event type: {event['type']}")
            expected, expected_source = resolve_events(facts, (event["subject"].casefold(), event["relation"].casefold()))
            target_fact_id = event.get("target_fact_id")
            if target_fact_id != expected_source:
                raise ValueError(
                    f"Fixture target mismatch for {event['query_id']}: "
                    f"declared {target_fact_id!r}, expected {expected_source!r}"
                )

            response = policy.respond(event, token_budget)
            success = response.answer == expected
            retrieval_correct = bool(
                target_fact_id is not None
                and response.answer == expected
                and response.source_fact_id == target_fact_id
            )
            corrupt = response.answer is not None and response.answer != expected
            row = {
                "query_id": event["query_id"],
                "query": event["text"],
                "subject": event["subject"],
                "relation": event["relation"],
                "target_fact_id": target_fact_id,
                "expected_answer": expected,
                "answer": response.answer,
                "source_fact_id": response.source_fact_id,
                "context_fact_ids": list(response.context_fact_ids),
                "context_tokens": response.context_tokens,
                "query_tokens": response.query_tokens,
                "tokens_used": response.tokens_used,
                "task_success": success,
                "retrieval_correct": retrieval_correct,
                "corrupt": corrupt,
            }
            rows.append(row)
            all_rows.append(row)

        episode_results.append(
            {
                "episode_id": episode["id"],
                "control": bool(episode.get("control", False)),
                "queries": rows,
                "metrics": summarize_queries(rows, token_budget),
                "memory": policy.inspect(),
            }
        )

    return {
        "schema_version": 1,
        "label": fixture_data["label"],
        "seed": fixture_data["seed"],
        "policy": policy_name,
        "token_budget": token_budget,
        "episode_results": episode_results,
        "metrics": summarize_queries(all_rows, token_budget),
        "protocol": {
            "cpu_only": True,
            "randomness": "None. The fixture seed is documented for reproducibility; no RNG is used.",
            "honesty": "Deterministic rules on synthetic episodes only. No trained models, real agent memory, real retrieval systems, or embeddings.",
        },
    }


def run_all(fixture_data: dict[str, Any], token_budget: int = 128) -> list[dict[str, Any]]:
    return [run_policy(fixture_data, name, token_budget) for name in POLICY_NAMES]
