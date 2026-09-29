"""Metric aggregation with definitions that can be checked from run records."""

from __future__ import annotations

from typing import Any, Iterable


def summarize_queries(rows: Iterable[dict[str, Any]], token_budget: int) -> dict[str, Any]:
    records = list(rows)
    count = len(records)
    successes = sum(bool(row["task_success"]) for row in records)
    answerable = [row for row in records if row["target_fact_id"] is not None]
    retrieval_hits = sum(bool(row["retrieval_correct"]) for row in answerable)
    memory_tokens = sum(int(row["context_tokens"]) for row in records)
    query_tokens = sum(int(row["query_tokens"]) for row in records)
    return {
        "query_count": count,
        "task_successes": successes,
        "task_success_rate": successes / count if count else 0.0,
        "answerable_queries": len(answerable),
        "retrieval_hits": retrieval_hits,
        "retrieval_accuracy": retrieval_hits / len(answerable) if answerable else None,
        "tokens_used": memory_tokens + query_tokens,
        "memory_tokens_used": memory_tokens,
        "query_tokens_used": query_tokens,
        "memory_token_budget_per_query": token_budget,
        "memory_token_budget_total": token_budget * count,
        "corruption_count": sum(bool(row["corrupt"]) for row in records),
    }


def metric_definitions() -> dict[str, str]:
    return {
        "task_success_rate": "Correct answers, including correct abstentions, divided by all queries.",
        "tokens_used": "Whitespace tokens in each query plus the memory entries shown for that query.",
        "memory_tokens_used": "Whitespace tokens in shown memory entries; this is compared with the per-query memory budget.",
        "retrieval_accuracy": "Queries with a planted target fact answered with that value and source fact ID, divided by answerable queries.",
        "corruption_count": "Non-empty answers that differ from the active planted value for the queried subject and relation.",
    }
