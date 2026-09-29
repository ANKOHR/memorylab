from __future__ import annotations

from memorylab.fixtures import default_episodes
from memorylab.runner import run_all, run_policy


def test_full_context_perfectly_solves_control_and_tokens_match_hand_count():
    run = run_policy(default_episodes(), "full_context", token_budget=128)
    control = next(episode for episode in run["episode_results"] if episode["episode_id"] == "control_basics")
    assert control["metrics"]["task_success_rate"] == 1.0
    assert [row["tokens_used"] for row in control["queries"]] == [15, 15]
    assert control["metrics"]["tokens_used"] == 30
    assert control["metrics"]["memory_tokens_used"] == 24


def test_summary_retrieval_accuracy_and_corruption_match_hand_computed_fixtures():
    run = run_policy(default_episodes(), "summary", token_budget=128)
    assert run["metrics"]["answerable_queries"] == 6
    assert run["metrics"]["retrieval_hits"] == 3
    assert run["metrics"]["retrieval_accuracy"] == 0.5
    assert run["metrics"]["corruption_count"] == 2
    trap = next(episode for episode in run["episode_results"] if episode["episode_id"] == "corruption_trap")
    assert trap["queries"][0]["answer"] == "South"
    assert trap["queries"][0]["expected_answer"] == "North"
    assert trap["metrics"]["corruption_count"] == 1


def test_full_context_does_not_corrupt_the_planted_trap_and_all_runs_exist():
    run = run_policy(default_episodes(), "full_context", token_budget=128)
    trap = next(episode for episode in run["episode_results"] if episode["episode_id"] == "corruption_trap")
    assert trap["queries"][0]["answer"] == "North"
    assert trap["metrics"]["corruption_count"] == 0
    all_runs = run_all(default_episodes(), 128)
    assert [item["policy"] for item in all_runs] == [
        "full_context",
        "summary",
        "token_overlap",
        "episodic",
        "structured",
        "hybrid",
    ]


def test_every_reported_query_token_count_matches_serialized_context_fields():
    run = run_policy(default_episodes(), "structured", token_budget=128)
    for episode in run["episode_results"]:
        for row in episode["queries"]:
            assert row["tokens_used"] == row["context_tokens"] + row["query_tokens"]
            assert row["context_tokens"] <= run["token_budget"]


def test_run_is_byte_deterministic_for_every_policy():
    import json

    for run in run_all(default_episodes(), 128):
        first = json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True)
        second = json.dumps(run_policy(default_episodes(), run["policy"], 128), ensure_ascii=False, indent=2, sort_keys=True)
        assert first == second
